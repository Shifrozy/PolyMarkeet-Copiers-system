"""
Redeem All Winning Positions
============================
Redeems resolved winning positions via CTF smart contract.
This converts winning outcome tokens back to USDC.
"""

import asyncio
import logging
from src.api.polymarket_client import PolymarketClient
from src.api.data_fetcher import DataFetcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


async def close_all_positions():
    client = PolymarketClient()
    fetcher = DataFetcher()

    # ─── Initialize ───
    logger.info("🔧 Initializing client...")
    if not await client.initialize():
        logger.error("❌ Failed to initialize. Check your .env file.")
        return

    await fetcher.initialize()
    wallet = client.wallet_address
    logger.info(f"👛 Wallet: {wallet}")

    # ─── Get balance before ───
    balance_before = await client.get_balance()
    logger.info(f"💰 Balance BEFORE: ${balance_before:.2f}")

    # ─── Fetch positions ───
    logger.info("🔍 Fetching your open positions...")
    positions = await fetcher.get_wallet_positions(wallet)

    if not positions:
        logger.info("✅ No open positions found.")
        await fetcher.close()
        return

    logger.info(f"📋 Found {len(positions)} positions\n")

    # ─── Categorize ───
    redeemable = []  # Resolved winners (price >= 0.95)
    losers = []      # Resolved losers (price <= 0.01)
    active = []      # Still active markets

    for pos in positions:
        if pos.size <= 0:
            continue
        if pos.current_price >= 0.95:
            redeemable.append(pos)
        elif pos.current_price <= 0.01:
            losers.append(pos)
        else:
            active.append(pos)

    logger.info("=" * 60)
    logger.info(f"  🟢 REDEEMABLE (winners):   {len(redeemable)} positions")
    logger.info(f"  🟡 ACTIVE (still open):    {len(active)} positions")
    logger.info(f"  🔴 LOST (worth $0):        {len(losers)} positions")
    logger.info("=" * 60)

    if redeemable:
        total_value = sum(p.size * p.current_price for p in redeemable)
        logger.info(f"\n💎 Total redeemable value: ~${total_value:.2f}")
    
    if losers:
        logger.info(f"\n⚠️  Lost positions (cannot redeem, worth $0):")
        for d in losers:
            logger.info(f"   ❌ {d.market_question[:50]} | {d.outcome} | {d.size:.1f} shares")
    
    if active:
        logger.info(f"\n🟡 Active positions (market still open):")
        for a in active:
            logger.info(f"   ⏳ {a.market_question[:50]} | {a.outcome} | {a.size:.1f} @ ${a.current_price:.3f}")

    if not redeemable:
        logger.info("\n✅ No redeemable positions. Nothing to do.")
        await fetcher.close()
        return

    # ─── Redeem via Smart Contract ───
    logger.info(f"\n🚀 Redeeming {len(redeemable)} winning positions...\n")
    success_count = 0
    fail_count = 0

    # Track unique condition IDs (avoid double redeem for same market)
    redeemed_conditions = set()

    for pos in redeemable:
        condition_id = pos.market_id
        
        if condition_id in redeemed_conditions:
            logger.info(f"   ⏭️ Already redeemed condition {condition_id[:12]}... (same market)")
            continue
        
        logger.info(f"� Redeeming: {pos.market_question[:50]}...")
        logger.info(f"   {pos.outcome} | {pos.size:.2f} shares | ~${pos.size * pos.current_price:.2f}")

        result = await client.redeem_position(condition_id)

        if result.get("success"):
            tx_hash = result.get("tx_hash", "unknown")
            logger.info(f"   ✅ Redeemed! TX: {tx_hash[:20]}...")
            success_count += 1
            redeemed_conditions.add(condition_id)
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"   ❌ Failed: {error}")
            fail_count += 1

    # ─── Final Report ───
    logger.info("")
    logger.info("=" * 60)
    logger.info(f"  ✅ Successfully redeemed: {success_count}")
    logger.info(f"  ❌ Failed:               {fail_count}")
    logger.info(f"  🔴 Lost (skipped):       {len(losers)}")
    logger.info(f"  🟡 Active (skipped):     {len(active)}")
    logger.info("=" * 60)

    # Wait for settlement
    await asyncio.sleep(5)

    balance_after = await client.get_balance()
    logger.info(f"\n💰 Balance BEFORE: ${balance_before:.2f}")
    logger.info(f"💰 Balance AFTER:  ${balance_after:.2f}")
    logger.info(f"💵 Recovered:      ${balance_after - balance_before:.2f}")

    await fetcher.close()
    logger.info("\n🏁 Done!")


if __name__ == "__main__":
    asyncio.run(close_all_positions())
