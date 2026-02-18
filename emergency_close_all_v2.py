import asyncio
import logging
from src.api.polymarket_client import PolymarketClient, Side
from src.api.data_fetcher import DataFetcher
from src.config import get_settings

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

async def close_all_positions():
    settings = get_settings()
    client = PolymarketClient()
    fetcher = DataFetcher()
    
    logger.info("🚨 EMERGENCY: CLOSING ALL POSITIONS VIA DATA API DISCOVERY...")
    
    if not await client.initialize():
        logger.error("❌ Failed to initialize client.")
        return
        
    await fetcher.initialize()
    
    wallet = client.wallet_address
    logger.info(f"👛 Target Wallet: {wallet}")

    # Discover positions via Data API
    positions = await fetcher.get_wallet_positions(wallet)
    
    if not positions:
        logger.info("✅ No open positions found via Data API.")
        # Try CLOB API as a last resort
        positions_clob = await client.get_positions()
        if not positions_clob:
            logger.info("✅ No open positions found via CLOB API either.")
            return
        else:
            logger.info(f"📋 Found {len(positions_clob)} positions via CLOB API.")
            # Map CLOB positions to a common format
            to_sell = []
            for p in positions_clob:
                to_sell.append({
                    "token_id": p.get("token_id"),
                    "size": float(p.get("size", 0))
                })
    else:
        logger.info(f"📋 Found {len(positions)} positions via Data API.")
        to_sell = []
        for p in positions:
            to_sell.append({
                "token_id": p.token_id,
                "size": p.size
            })

    # Liquidate
    for item in to_sell:
        tid = item["token_id"]
        qty = item["size"]
        
        if qty <= 0.1: # Skip tiny dust
            continue
            
        logger.info(f"📉 SELLING {qty} of {tid}...")
        res = await client.place_market_order(
            token_id=tid,
            side=Side.SELL,
            amount=qty
        )
        
        if res.success:
            logger.info(f"✅ SOLD {tid}")
        else:
            logger.error(f"❌ FAILED TO SELL {tid}: {res.error}")

    logger.info("🏁 EMERGENCY LIQUIDATION FINISHED.")
    balance = await client.get_balance()
    logger.info(f"💰 Current Balance: ${balance:,.2f}")
    
    await fetcher.stop()

if __name__ == "__main__":
    asyncio.run(close_all_positions())
