"""Check approval TX and continue bridge."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import get_settings
from eth_account import Account
from web3 import Web3

s = get_settings()
pk = s.private_key
if not pk.startswith('0x'):
    pk = '0x' + pk
account = Account.from_key(pk)
wallet = account.address

USDC_ETH = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
ROOT_CHAIN_MANAGER = "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77"
ERC20_PREDICATE = "0x40ec5B33f54e0E8A33A975908C5BA1c14e5BbbDf"

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
     "type": "function"},
    {"constant": True,
     "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "remaining", "type": "uint256"}],
     "type": "function"},
]

DEPOSIT_ABI = [
    {"inputs": [
        {"name": "user", "type": "address"},
        {"name": "rootToken", "type": "address"},
        {"name": "depositData", "type": "bytes"}
    ],
     "name": "depositFor",
     "outputs": [],
     "stateMutability": "nonpayable",
     "type": "function"},
]

# Try multiple RPCs
rpcs = [
    "https://rpc.ankr.com/eth",
    "https://ethereum-rpc.publicnode.com",
    "https://1rpc.io/eth",
    "https://eth.llamarpc.com",
]

w3 = None
for rpc in rpcs:
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
        if w3.is_connected():
            print(f"Connected to: {rpc}")
            break
    except:
        continue

if not w3 or not w3.is_connected():
    print("Cannot connect to any Ethereum RPC!")
    sys.exit(1)

# Check approval TX
approval_tx = "0xcba33d4ba2fc07fe7e0d3fd9cbeed0bc62322c0c16eb0b8b1e9e2139242e3b1a"
print(f"Checking approval TX: {approval_tx[:20]}...")

for attempt in range(10):
    try:
        receipt = w3.eth.get_transaction_receipt(approval_tx)
        if receipt:
            status = "SUCCESS" if receipt["status"] == 1 else "FAILED"
            print(f"Approval TX: {status} (Gas: {receipt['gasUsed']})")
            break
    except:
        pass
    print(f"  Waiting... ({attempt+1}/10)")
    time.sleep(5)

# Check allowance
usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ETH), abi=ERC20_ABI)
allowance = usdc.functions.allowance(wallet, Web3.to_checksum_address(ERC20_PREDICATE)).call()
usdc_balance = usdc.functions.balanceOf(wallet).call()

print(f"USDC Balance: ${usdc_balance / 1e6:.2f}")
print(f"Allowance: ${allowance / 1e6:.2f}")

if allowance < usdc_balance:
    print("Allowance not enough - approval may still be pending")
    print("Waiting 30 more seconds...")
    time.sleep(30)
    allowance = usdc.functions.allowance(wallet, Web3.to_checksum_address(ERC20_PREDICATE)).call()
    print(f"Allowance now: ${allowance / 1e6:.2f}")

if allowance >= usdc_balance and usdc_balance > 0:
    print()
    print("=" * 50)
    print("APPROVAL CONFIRMED! Now bridging...")
    print("=" * 50)
    
    rcm = w3.eth.contract(
        address=Web3.to_checksum_address(ROOT_CHAIN_MANAGER),
        abi=DEPOSIT_ABI
    )
    
    deposit_data = Web3.to_bytes(usdc_balance).rjust(32, b'\x00')
    
    nonce = w3.eth.get_transaction_count(wallet)
    gas_price = w3.eth.gas_price
    gas_price = int(gas_price * 1.15)
    
    try:
        gas_est = rcm.functions.depositFor(
            wallet,
            Web3.to_checksum_address(USDC_ETH),
            deposit_data
        ).estimate_gas({"from": wallet})
        gas_limit = int(gas_est * 1.3)
    except:
        gas_limit = 150000
    
    est_cost = (gas_limit * gas_price) / 1e18
    print(f"Gas estimate: {est_cost:.6f} ETH")
    
    deposit_tx = rcm.functions.depositFor(
        wallet,
        Web3.to_checksum_address(USDC_ETH),
        deposit_data
    ).build_transaction({
        "from": wallet,
        "nonce": nonce,
        "gasPrice": gas_price,
        "gas": gas_limit,
        "chainId": 1
    })
    
    signed = w3.eth.account.sign_transaction(deposit_tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Bridge TX sent: {tx_hash.hex()}")
    print("Waiting for confirmation...")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    
    if receipt["status"] == 1:
        cost = (receipt["gasUsed"] * receipt["effectiveGasPrice"]) / 1e18
        print()
        print("=" * 50)
        print("BRIDGE SUCCESSFUL!")
        print("=" * 50)
        print(f"Amount: ${usdc_balance / 1e6:.2f} USDC")
        print(f"TX: {tx_hash.hex()}")
        print(f"Gas: {cost:.6f} ETH")
        print()
        print("USDC will arrive on Polygon in ~20-30 minutes!")
        print(f"Track: https://etherscan.io/tx/{tx_hash.hex()}")
    else:
        print(f"BRIDGE FAILED! TX: {tx_hash.hex()}")
        print("Your USDC is safe.")
else:
    print("Cannot proceed - approval not confirmed or no USDC balance")
