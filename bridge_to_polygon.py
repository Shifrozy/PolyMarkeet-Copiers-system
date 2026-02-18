"""
Bridge USDC from Ethereum to Polygon
=====================================
Uses the official Polygon PoS Bridge to move USDC from Ethereum to Polygon.
This is safe and battle-tested — the same bridge Polymarket uses.

Process:
1. Approve USDC for the bridge contract
2. Deposit USDC into Polygon bridge
3. Wait ~20-30 minutes for USDC to appear on Polygon as USDC.e
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import get_settings
from eth_account import Account
from web3 import Web3

# ─── Ethereum Contracts ─────────────────────────────────────────────
USDC_ETH = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
ROOT_CHAIN_MANAGER = "0xA0c68C638235ee32657e8f720a23ceC1bFc77C77"
ERC20_PREDICATE = "0x40ec5B33f54e0E8A33A975908C5BA1c14e5BbbDf"

# ─── ABIs ────────────────────────────────────────────────────────────
ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
     "type": "function"},
    {"constant": True,
     "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "remaining", "type": "uint256"}],
     "type": "function"},
    {"constant": False,
     "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
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


def main():
    s = get_settings()
    pk = s.private_key
    if not pk.startswith('0x'):
        pk = '0x' + pk

    account = Account.from_key(pk)
    wallet = account.address

    # Connect to Ethereum
    eth_rpc = "https://eth.llamarpc.com"
    w3 = Web3(Web3.HTTPProvider(eth_rpc, request_kwargs={"timeout": 30}))

    if not w3.is_connected():
        print("  [X] Cannot connect to Ethereum RPC!")
        return

    print("=" * 60)
    print("  BRIDGE USDC: ETHEREUM -> POLYGON")
    print("=" * 60)
    print(f"  Wallet: {wallet}")
    print(f"  Network: Ethereum Mainnet")
    print()

    # ─── Check Balances ─────────────────────────────────────────────
    eth_balance = w3.eth.get_balance(wallet)
    eth_amount = float(Web3.from_wei(eth_balance, 'ether'))

    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ETH), abi=ERC20_ABI)
    usdc_raw = usdc.functions.balanceOf(wallet).call()
    usdc_amount = usdc_raw / 1e6

    print(f"  ETH Balance:  {eth_amount:.6f} ETH (${eth_amount * 2700:.2f} approx)")
    print(f"  USDC Balance: ${usdc_amount:.2f}")
    print()

    if usdc_amount < 1:
        print("  [X] No USDC to bridge!")
        return

    if eth_amount < 0.002:
        print("  [X] Not enough ETH for gas! Need at least 0.002 ETH")
        return

    # ─── Calculate Bridge Amount ─────────────────────────────────────
    bridge_amount = usdc_raw  # Bridge ALL USDC
    bridge_display = usdc_amount

    print(f"  Will bridge: ${bridge_display:.2f} USDC")
    print(f"  From: Ethereum")
    print(f"  To:   Polygon (arrives as USDC.e)")
    print(f"  Time: ~20-30 minutes after confirmation")
    print()
    print("  Gas cost: ~$1-3 in ETH")
    print()

    confirm = input("  Proceed with bridge? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("  Cancelled.")
        return

    # ─── Step 1: Approve USDC for Bridge ─────────────────────────────
    print()
    print("  [1/2] Approving USDC for Polygon Bridge...")

    # Check existing allowance
    allowance = usdc.functions.allowance(
        wallet, Web3.to_checksum_address(ERC20_PREDICATE)
    ).call()

    if allowance < bridge_amount:
        nonce = w3.eth.get_transaction_count(wallet)
        gas_price = w3.eth.gas_price

        # Add 10% buffer to gas price for faster confirmation
        gas_price = int(gas_price * 1.1)

        approve_tx = usdc.functions.approve(
            Web3.to_checksum_address(ERC20_PREDICATE),
            bridge_amount
        ).build_transaction({
            'from': wallet,
            'nonce': nonce,
            'gasPrice': gas_price,
            'gas': 60000,
            'chainId': 1  # Ethereum mainnet
        })

        signed = w3.eth.account.sign_transaction(approve_tx, account.key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"  Approval TX: {tx_hash.hex()}")
        print("  Waiting for confirmation...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt['status'] != 1:
            print("  [X] Approval failed!")
            return
        print(f"  [OK] Approved! Gas used: {receipt['gasUsed']}")
    else:
        print("  [OK] Already approved!")

    # ─── Step 2: Deposit to Bridge ───────────────────────────────────
    print()
    print("  [2/2] Depositing USDC to Polygon Bridge...")

    rcm = w3.eth.contract(
        address=Web3.to_checksum_address(ROOT_CHAIN_MANAGER),
        abi=DEPOSIT_ABI
    )

    # Encode the deposit amount as bytes (abi.encode uint256)
    deposit_data = Web3.to_bytes(bridge_amount).rjust(32, b'\x00')

    nonce = w3.eth.get_transaction_count(wallet)
    gas_price = w3.eth.gas_price
    gas_price = int(gas_price * 1.1)

    # Estimate gas
    try:
        gas_estimate = rcm.functions.depositFor(
            wallet,
            Web3.to_checksum_address(USDC_ETH),
            deposit_data
        ).estimate_gas({'from': wallet})
        gas_limit = int(gas_estimate * 1.3)  # 30% buffer
    except Exception as e:
        print(f"  Gas estimation: {e}")
        gas_limit = 150000  # Safe default

    deposit_tx = rcm.functions.depositFor(
        wallet,
        Web3.to_checksum_address(USDC_ETH),
        deposit_data
    ).build_transaction({
        'from': wallet,
        'nonce': nonce,
        'gasPrice': gas_price,
        'gas': gas_limit,
        'chainId': 1
    })

    # Show gas cost estimate
    estimated_cost = (gas_limit * gas_price) / 1e18
    print(f"  Estimated gas cost: {estimated_cost:.6f} ETH (~${estimated_cost * 2700:.2f})")

    signed = w3.eth.account.sign_transaction(deposit_tx, account.key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"  Bridge TX: {tx_hash.hex()}")
    print("  Waiting for confirmation...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

    if receipt['status'] == 1:
        actual_cost = (receipt['gasUsed'] * receipt['effectiveGasPrice']) / 1e18
        print()
        print("  " + "=" * 50)
        print(f"  [OK] BRIDGE SUCCESSFUL!")
        print("  " + "=" * 50)
        print(f"  Amount:   ${bridge_display:.2f} USDC")
        print(f"  TX Hash:  {tx_hash.hex()}")
        print(f"  Gas Used: {receipt['gasUsed']} ({actual_cost:.6f} ETH)")
        print()
        print("  USDC will appear on Polygon in ~20-30 minutes")
        print("  as USDC.e (bridged USDC)")
        print()
        print("  Track: https://etherscan.io/tx/" + tx_hash.hex())
        print()
        print("  NEXT STEPS:")
        print("  1. Wait 20-30 min for USDC to arrive on Polygon")
        print("  2. You still need POL for gas on Polygon")
        print("     (Buy ~$1 POL from exchange, send to Polygon)")
        print("  3. Run: python check_wallet.py")
        print("  4. Run: python check_wallet.py --approve")
        print("  5. Run: python main.py")
    else:
        print()
        print(f"  [X] BRIDGE TRANSACTION FAILED!")
        print(f"  TX: {tx_hash.hex()}")
        print("  Your USDC is safe - it was not moved.")
        print("  Check: https://etherscan.io/tx/" + tx_hash.hex())

    print()


if __name__ == "__main__":
    main()
