"""
Wallet Setup Checker
====================
Run this script to check if your MetaMask wallet is ready for Polymarket trading.

Usage:
    python check_wallet.py          Check wallet status
    python check_wallet.py --approve  Approve USDC for Polymarket (one-time)
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def check_wallet():
    """Check wallet readiness."""
    from src.api.polymarket_client import PolymarketClient
    from src.config import get_settings
    
    settings = get_settings()
    
    print()
    print("=" * 60)
    print("  POLYMARKET WALLET SETUP CHECKER")
    print("=" * 60)
    
    # Check private key
    if not settings.private_key:
        print("\n  [X] PRIVATE_KEY is not set in .env file!")
        print("      Add your MetaMask private key to .env:")
        print("      PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE")
        print()
        print("  HOW TO GET YOUR PRIVATE KEY:")
        print("  1. Open MetaMask extension")
        print("  2. Click on 3 dots (...) > Account Details")
        print("  3. Click 'Show Private Key'")
        print("  4. Enter your MetaMask password")
        print("  5. Copy the key and paste it in .env")
        print()
        return
    
    wallet_type = getattr(settings, 'wallet_type', 'metamask')
    print(f"\n  Wallet Mode: {wallet_type.upper()}")
    
    # Initialize client
    client = PolymarketClient()
    print("  Initializing client...")
    
    success = await client.initialize()
    if not success:
        print("  [X] Failed to initialize client!")
        return
    
    print(f"  Wallet Address: {client.wallet_address}")
    
    # Check wallet readiness
    print("\n  Checking wallet readiness...\n")
    result = await client.check_wallet_ready()
    
    # ─── Display Results ───
    print("  " + "-" * 56)
    
    # MATIC Balance
    matic = result["matic_balance"]
    matic_ok = matic >= 0.01
    icon = "[OK]" if matic_ok else "[X] "
    print(f"  {icon} MATIC (gas):  {matic:.6f} MATIC")
    if matic_ok:
        print(f"       Enough for ~{int(matic / 0.0001)} transactions")
    else:
        print("       NEED: Send at least 0.5 MATIC to this wallet on Polygon")
    
    print()
    
    # USDC Balance
    usdc = result["usdc_balance"]
    usdc_ok = usdc >= 1.0
    icon = "[OK]" if usdc_ok else "[X] "
    print(f"  {icon} USDC:        ${usdc:,.2f}")
    if usdc_ok:
        max_trade = settings.max_trade_amount
        trades_possible = int(usdc / max_trade) if max_trade > 0 else 0
        print(f"       Can execute ~{trades_possible} trades at ${max_trade} each")
    else:
        print("       NEED: Send USDC to this wallet on Polygon network")
        print("       NOTE: Must be USDC on POLYGON, not Ethereum!")
    
    print()
    
    # USDC Approval
    approved = result["usdc_approved"]
    icon = "[OK]" if approved else "[X] "
    print(f"  {icon} USDC Approved: {'Yes' if approved else 'No'}")
    if not approved:
        print("       NEED: Run 'python check_wallet.py --approve'")
        print("       This is a one-time transaction (~$0.001 gas)")
    
    print("\n  " + "-" * 56)
    
    # Overall Status
    if result["ready"]:
        print("\n  [READY] Your wallet is fully set up for trading!")
        print("  You can now run: python main.py")
    else:
        print("\n  [NOT READY] Fix the issues above before trading.")
        
        if result["recommendations"]:
            print("\n  RECOMMENDATIONS:")
            for i, rec in enumerate(result["recommendations"], 1):
                print(f"  {i}. {rec}")
    
    print()
    
    # ─── Quick Setup Guide ───
    if not result["ready"]:
        print("  " + "=" * 56)
        print("  QUICK SETUP GUIDE:")
        print("  " + "=" * 56)
        print()
        print("  Step 1: Add MATIC for gas")
        print("  - Open MetaMask")
        print("  - Switch to Polygon network")
        print("  - Buy or bridge MATIC (only need ~$0.50 worth)")
        print()
        print("  Step 2: Add USDC on Polygon")
        print("  - Buy USDC on a CEX (Binance/Coinbase)")
        print("  - Withdraw USDC to your MetaMask on POLYGON network")
        print("  - Or bridge USDC from Ethereum via bridge.polygon.technology")
        print()
        print("  Step 3: Approve USDC for Polymarket")
        print("  - Run: python check_wallet.py --approve")
        print("  - This sends 2 approval transactions (costs <$0.01)")
        print()
        print("  Step 4: Start the bot!")
        print("  - Run: python main.py")
        print()


async def approve_usdc():
    """Run USDC approval for Polymarket."""
    from src.api.polymarket_client import PolymarketClient
    
    print()
    print("=" * 60)
    print("  USDC APPROVAL FOR POLYMARKET")
    print("=" * 60)
    print()
    print("  This will approve Polymarket's exchange contracts")
    print("  to spend your USDC for trading.")
    print()
    print("  - Cost: ~$0.001 (MATIC gas on Polygon)")
    print("  - Frequency: One-time only")
    print("  - Security: Standard ERC-20 approval (same as any DEX)")
    print()
    
    confirm = input("  Proceed? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("  Cancelled.")
        return
    
    client = PolymarketClient()
    print("\n  Initializing...")
    
    if not await client.initialize():
        print("  [X] Failed to initialize! Check your PRIVATE_KEY in .env")
        return
    
    print(f"  Wallet: {client.wallet_address}")
    print()
    
    # Check MATIC balance first
    matic = await client.get_matic_balance()
    if matic < 0.001:
        print(f"  [X] Not enough MATIC for gas! Balance: {matic:.6f}")
        print("      Send at least 0.01 MATIC to your wallet first.")
        return
    
    print(f"  MATIC balance: {matic:.6f} (OK)")
    print()
    print("  Sending approval transactions...")
    print()
    
    result = await client.approve_usdc(unlimited=True)
    
    if result["success"]:
        print()
        print("  " + "=" * 56)
        print("  [OK] USDC APPROVED SUCCESSFULLY!")
        print("  " + "=" * 56)
        
        if "details" in result:
            for name, detail in result["details"].items():
                print(f"  {name}: TX {detail['tx_hash']}")
        
        print()
        print("  You can now start the bot: python main.py")
    else:
        print(f"\n  [X] Approval failed: {result.get('error')}")
        print("  Try again or approve manually on PolygonScan.")
    
    print()


def main():
    parser = argparse.ArgumentParser(description="Check wallet setup for Polymarket")
    parser.add_argument("--approve", action="store_true", help="Approve USDC for Polymarket")
    args = parser.parse_args()
    
    if args.approve:
        asyncio.run(approve_usdc())
    else:
        asyncio.run(check_wallet())


if __name__ == "__main__":
    main()
