"""
Direct USDC Approval for Polymarket
====================================
Standalone script - no dependency on PolymarketClient initialization.
Directly approves USDC for both Polymarket exchange contracts.
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import get_settings
from eth_account import Account
from web3 import Web3

# Polygon Contracts
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982e"
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"

APPROVE_ABI = [
    {"constant": False,
     "inputs": [{"name": "_spender", "type": "address"}, {"name": "_value", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
     "type": "function"},
    {"constant": True,
     "inputs": [{"name": "_owner", "type": "address"}, {"name": "_spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "remaining", "type": "uint256"}],
     "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
     "type": "function"},
]


def main():
    s = get_settings()
    pk = s.private_key
    if not pk.startswith('0x'):
        pk = '0x' + pk
    
    account = Account.from_key(pk)
    wallet = account.address
    
    # Try multiple Polygon RPCs
    rpcs = [
        "https://polygon-rpc.com",
        "https://rpc.ankr.com/polygon",
        "https://polygon-mainnet.public.blastapi.io",
        "https://1rpc.io/matic"
    ]
    
    w3 = None
    for rpc in rpcs:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 20}))
            if w3.is_connected():
                print(f"  Connected to: {rpc}")
                break
        except:
            continue
            
    if not w3 or not w3.is_connected():
        print("  [X] Cannot connect to any Polygon RPC!")
        return
    
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=APPROVE_ABI)
    
    bal = usdc.functions.balanceOf(wallet).call()
    pol_bal = float(Web3.from_wei(w3.eth.get_balance(wallet), 'ether'))
    print(f"  USDC: ${bal / 1e6:.2f}")
    print(f"  POL:  {pol_bal:.4f}")
    print()
    
    MAX_UINT256 = 2**256 - 1
    
    exchanges = [
        ("CTF Exchange", CTF_EXCHANGE),
        ("Neg Risk Exchange", NEG_RISK_CTF_EXCHANGE),
    ]
    
    for name, addr in exchanges:
        checksum_addr = Web3.to_checksum_address(addr)
        
        # Check current allowance
        try:
            current = usdc.functions.allowance(wallet, checksum_addr).call()
            if current > 1_000_000 * 1e6:
                print(f"  [OK] {name}: Already approved!")
                continue
        except Exception as e:
            print(f"  [!] Error checking allowance for {name}: {e}")
            time.sleep(5)
        
        print(f"  Approving {name}...")
        
        try:
            nonce = w3.eth.get_transaction_count(wallet)
            # Fetch fresh gas price
            gas_price = w3.eth.gas_price
            
            # During congestion, we need to be aggressive. 
            # Use current gas price + 50%
            aggressive_gas_price = int(gas_price * 1.5)
            
            # Ensure it's at least 400 Gwei if the network is really spikey
            if aggressive_gas_price < 400 * 1e9:
                aggressive_gas_price = int(400 * 1e9)
                
            print(f"  Using Gas Price: {aggressive_gas_price / 1e9:.2f} Gwei")
            
            tx = usdc.functions.approve(
                checksum_addr, MAX_UINT256
            ).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gasPrice': aggressive_gas_price,
                'gas': 100000, # More generous gas limit
                'chainId': 137
            })
            
            signed = w3.eth.account.sign_transaction(tx, account.key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
            print(f"  TX: {tx_hash.hex()}")
            print("  Waiting for confirmation...")
            
            # Wait with a longer timeout
            receipt = None
            for _ in range(12): # 120 seconds total
                try:
                    receipt = w3.eth.get_transaction_receipt(tx_hash)
                    if receipt: break
                except:
                    pass
                time.sleep(10)
            
            if receipt and receipt['status'] == 1:
                cost = (receipt['gasUsed'] * receipt['effectiveGasPrice']) / 1e18
                print(f"  [OK] {name} approved! Gas: {cost:.6f} POL")
            else:
                print(f"  [X] {name} FAILED or timed out! Check PolygonScan.")
            
        except Exception as e:
            print(f"  [X] Error during {name} approval: {str(e)}")
            
        # Give the RPC a break
        print("  Waiting 10s before next step...")
        time.sleep(10)
    
    # Verify
    print("-" * 55)
    for name, addr in exchanges:
        checksum_addr = Web3.to_checksum_address(addr)
        allowance = usdc.functions.allowance(wallet, checksum_addr).call()
        ok = allowance > 1_000_000 * 1e6
        status = "APPROVED" if ok else "NOT APPROVED"
        print(f"  {name}: {status}")
    
    print()
    print("=" * 55)
    print("  ALL DONE! Bot is ready to start!")
    print("  Run: python main.py")
    print("=" * 55)
    print()


if __name__ == "__main__":
    main()
