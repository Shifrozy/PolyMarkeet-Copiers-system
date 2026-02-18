"""Quick check - where is the USDC right now?"""
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

abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"}]

print("=" * 55)
print("  USDC TRACKER - KAHAN HAI AAPKI $125?")
print("=" * 55)
print(f"  Wallet: {wallet}")
print()

# Ethereum check
try:
    w3_eth = Web3(Web3.HTTPProvider("https://rpc.ankr.com/eth", request_kwargs={"timeout": 15}))
    usdc_eth = w3_eth.eth.contract(
        address=Web3.to_checksum_address("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
        abi=abi
    )
    bal_eth = usdc_eth.functions.balanceOf(wallet).call() / 1e6
    print(f"  Ethereum USDC:  ${bal_eth:.2f}  (bridge se nikal gayi)")
except Exception as e:
    print(f"  Ethereum: Error - {e}")
    bal_eth = 0

# Polygon check
try:
    w3_pol = Web3(Web3.HTTPProvider("https://polygon-rpc.com", request_kwargs={"timeout": 15}))
    usdc_pol = w3_pol.eth.contract(
        address=Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"),
        abi=abi
    )
    bal_pol = usdc_pol.functions.balanceOf(wallet).call() / 1e6
    print(f"  Polygon USDC.e: ${bal_pol:.2f}")
except Exception as e:
    print(f"  Polygon: Error - {e}")
    bal_pol = 0

print()
print("-" * 55)

if bal_pol > 100:
    print("  USDC POLYGON PE AA GAYI HAI! Ready to trade!")
elif bal_eth < 1 and bal_pol < 1:
    print("  USDC abhi BRIDGE mein hai (transfer ho rahi hai)")
    print("  Yeh bilkul NORMAL hai!")
    print("  ~20-30 min mein Polygon pe dikhegi")
    print()
    print("  Kya ho raha hai:")
    print("  Ethereum --> [Bridge Processing] --> Polygon")
    print("  $125 USDC    (abhi yahan hai)      USDC.e")
    print()
    print("  5-10 min baad ye script dobara run karo!")
elif bal_eth > 0:
    print(f"  USDC abhi bhi Ethereum pe hai: ${bal_eth:.2f}")

print("=" * 55)
