"""Quick diagnostic to check all balances on the wallet."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import get_settings
from eth_account import Account
from web3 import Web3
import requests

s = get_settings()
pk = s.private_key
if not pk.startswith('0x'):
    pk = '0x' + pk

account = Account.from_key(pk)
w3 = Web3(Web3.HTTPProvider(s.rpc_url))

print("=" * 60)
print("  WALLET BALANCE DIAGNOSTIC")
print("=" * 60)
print(f"  Your Wallet: {account.address}")
print(f"  RPC Connected: {w3.is_connected()}")
print()

# Check all token balances
abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"}]

tokens = {
    "USDC.e (bridged)": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "USDC (native)":    "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
    "USDT":             "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
}

print("  --- Token Balances ---")
for name, addr in tokens.items():
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
        bal = contract.functions.balanceOf(account.address).call()
        print(f"  {name}: ${bal / 1e6:.2f}")
    except Exception as e:
        print(f"  {name}: ERROR - {e}")

# MATIC
try:
    matic = w3.eth.get_balance(account.address)
    matic_eth = float(Web3.from_wei(matic, 'ether'))
    print(f"  MATIC/POL: {matic_eth:.6f} MATIC")
except Exception as e:
    print(f"  MATIC: ERROR - {e}")

# Check Polymarket proxy wallet
print()
print("  --- Polymarket Profile Check ---")
try:
    resp = requests.get(
        f"https://data-api.polymarket.com/profile?address={account.address.lower()}",
        timeout=10
    )
    if resp.status_code == 200:
        data = resp.json()
        proxy = data.get("proxyWallet") or data.get("proxy_wallet") or data.get("polyProxyAddress")
        if proxy:
            print(f"  Polymarket Proxy Wallet: {proxy}")
            for name, addr in tokens.items():
                try:
                    contract = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
                    bal = contract.functions.balanceOf(Web3.to_checksum_address(proxy)).call()
                    if bal > 0:
                        print(f"  Proxy {name}: ${bal / 1e6:.2f}")
                except:
                    pass
        else:
            print("  No proxy wallet found (not registered on Polymarket yet)")
    else:
        print(f"  Profile API returned status {resp.status_code}")
except Exception as e:
    print(f"  Profile check error: {e}")

# Also check the target wallet to make sure data API works
print()
print("  --- Target Wallet Check ---")
target = s.target_wallet_address
print(f"  Target: {target}")
try:
    resp = requests.get(
        f"https://data-api.polymarket.com/activity?address={target.lower()}&limit=3",
        timeout=10
    )
    if resp.status_code == 200:
        data = resp.json()
        if data:
            print(f"  Target has {len(data)} recent activities - API works!")
        else:
            print("  No recent activities found for target")
    else:
        print(f"  Activity API returned status {resp.status_code}")
except Exception as e:
    print(f"  Target check error: {e}")

print()
print("=" * 60)
print("  DIAGNOSIS:")
print("=" * 60)

all_zero = True
for name, addr in tokens.items():
    try:
        contract = w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)
        bal = contract.functions.balanceOf(account.address).call()
        if bal > 0:
            all_zero = False
    except:
        pass

if all_zero:
    print()
    print("  [!] Your wallet has NO tokens on Polygon network!")
    print()
    print("  Possible reasons:")
    print("  1. Funds are on ETHEREUM mainnet (not Polygon)")
    print("     -> Bridge to Polygon via bridge.polygon.technology")
    print("  2. Funds are in a DIFFERENT MetaMask account")
    print("     -> Check which account has the funds")
    print("  3. Funds are deposited on Polymarket website")
    print("     -> Those sit in a proxy wallet, not your EOA")
    print("  4. Wrong private key in .env")
    print("     -> Verify in MetaMask: Account Details > Show Private Key")
    print()
    print("  YOUR WALLET ADDRESS: " + account.address)
    print("  Open MetaMask and check if this matches your funded account!")
else:
    print("  Tokens found! Check balances above.")

print()
