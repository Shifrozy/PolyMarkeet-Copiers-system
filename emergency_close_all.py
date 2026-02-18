import asyncio
import logging
from src.api.polymarket_client import PolymarketClient, Side
from src.config import get_settings

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

async def close_all_positions():
    client = PolymarketClient()
    
    logger.info("🚨 EMERGENCY: Initializing client to close all positions...")
    if not await client.initialize():
        logger.error("❌ Failed to initialize Polymarket client.")
        return

    # Get positions
    logger.info("🔍 Fetching current open positions...")
    positions = await client.get_positions()
    
    if not positions:
        logger.info("✅ No open positions found.")
        return

    logger.info(f"📋 Found {len(positions)} position entries. Starting liquidation...")
    
    for pos in positions:
        token_id = pos.get("token_id")
        size = float(pos.get("size", 0))
        
        if size <= 0:
            continue
            
        logger.info(f"📉 Closing position: {token_id} | Size: {size}")
        
        # Place market sell order
        result = await client.place_market_order(
            token_id=token_id,
            side=Side.SELL,
            amount=size # size is number of shares
        )
        
        if result.success:
            logger.info(f"✅ Successfully sold {size} shares of {token_id}")
        else:
            logger.error(f"❌ Failed to sell {token_id}: {result.error}")

    logger.info("🏁 Emergency liquidation complete.")
    # Check balance
    balance = await client.get_balance()
    logger.info(f"💰 Final Balance: ${balance:,.2f}")

if __name__ == "__main__":
    asyncio.run(close_all_positions())
