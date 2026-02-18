"""Check USDC on ALL networks to find where the 124 USDC is."""
import sys, os
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

print("=" * 60)
print("  FINDING YOUR 124 USDC - ALL NETWORKS")
print("=" * 60)
print(f"  Wallet: {wallet}")
print()

abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"}]

networks = {
    "Polygon": {
        "rpc": "https://polygon-rpc.com",
        "usdc": [
            ("USDC.e (bridged)", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6),
            ("USDC (native)", "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
        ],
        "native": "POL/MATIC"
    },
    "Ethereum": {
        "rpc": "https://eth.llamarpc.com",
        "usdc": [
            ("USDC", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),
        ],
        "native": "ETH"
    },
    "Arbitrum": {
        "rpc": "https://arb1.arbitrum.io/rpc",
        "usdc": [
            ("USDC", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),
            ("USDC.e", "0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8", 6),
        ],
        "native": "ETH"
    },
    "Base": {
        "rpc": "https://mainnet.base.org",
        "usdc": [
            ("USDC", "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", 6),
        ],
        "native": "ETH"
    },
    "BSC": {
        "rpc": "https://bsc-dataseed.binance.org",
        "usdc": [
            ("USDC", "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", 18),
        ],
        "native": "BNB"
    },
    "Optimism": {
        "rpc": "https://mainnet.optimism.io",
        "usdc": [
            ("USDC", "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85", 6),
            ("USDC.e", "0x7F5c764cBc14f9669B88837ca1490cCa17c31607", 6),
        ],
        "native": "ETH"
    },
}

found_usdc = None

for net_name, net_info in networks.items():
    try:
        w3 = Web3(Web3.HTTPProvider(net_info["rpc"], request_kwargs={"timeout": 8}))
        if not w3.is_connected():
            print(f"  [{net_name}] Cannot connect")
            continue
        
        # Check native balance
        native_bal = w3.eth.get_balance(wallet)
        native_amount = float(Web3.from_wei(native_bal, 'ether'))
        
        # Check USDC tokens
        for token_name, token_addr, decimals in net_info["usdc"]:
            try:
                contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_addr), abi=abi
                )
                bal = contract.functions.balanceOf(wallet).call()
                amount = bal / (10 ** decimals)
                
                if amount > 0:
                    print(f"  [{net_name}] {token_name}: ${amount:,.2f}  <-- FOUND!")
                    found_usdc = net_name
                else:
                    print(f"  [{net_name}] {token_name}: $0.00")
            except Exception as e:
                print(f"  [{net_name}] {token_name}: Error")
        
        if native_amount > 0.0001:
            print(f"  [{net_name}] {net_info['native']}: {native_amount:.6f}")
        else:
            print(f"  [{net_name}] {net_info['native']}: 0")
        
        print()
        
    except Exception as e:
        print(f"  [{net_name}] Error: {e}")
        print()

print("=" * 60)
if found_usdc:
    print(f"  FOUND! Your USDC is on: {found_usdc}")
    if found_usdc != "Polygon":
        print(f"  You need to BRIDGE it to Polygon for Polymarket!")
        print()
        print(f"  STEPS:")
        print(f"  1. Get gas on {found_usdc} (need tiny amount for bridge tx)")
        print(f"  2. Bridge USDC from {found_usdc} -> Polygon")
        print(f"  3. Also get some POL on Polygon for gas")
else:
    print("  USDC NOT FOUND on any network!")
    print()
    print("  This means the USDC is in a DIFFERENT MetaMask account.")
    print(f"  The private key in .env maps to: {wallet}")
    print()
    print("  FIX: Open MetaMask > find which account has 124 USDC")
    print("  > Copy THAT account's private key > Paste in .env")
print("=" * 60)
print()
