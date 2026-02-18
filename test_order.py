"""
Manual Order Tester
===================
Attempts to place a $1 test order to verify the full trading pipeline.
"""
import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.polymarket_client import PolymarketClient, Side
from src.api.data_fetcher import DataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("OrderTester")

async def test_order():
    client = PolymarketClient()
    fetcher = DataFetcher()
    await fetcher.initialize()
    
    logger.info("Initializing client...")
    if not await client.initialize():
        logger.error("Failed to initialize client")
        return

    if not client.clob_client:
        logger.error("Client has no CLOB connection (Auth failed)")
        return

    # Find a liquid market
    logger.info("Fetching active markets...")
    markets = await fetcher.get_active_markets(limit=50)
    if not markets:
        logger.error("No active markets found")
        return
    
    logger.info(f"Found {len(markets)} active markets")
    
    # Filter for a market that is actually tradeable on CLOB
    test_token_id = None
    test_market = None
    
    # Try to find a liquid market like BTC or Crypto
    for m in markets:
        # Gamma API sometimes puts IDs in tokens, sometimes clobTokenIds
        ids = m.tokens
        if not ids:
            # Check if we can get it from internal cache or raw data if we had it
            # For now, let's just find the first one that HAS tokens
            continue
            
        if len(ids) >= 2:
            test_market = m
            test_token_id = ids[0]
            break
            
    if not test_token_id:
        logger.error("No suitabe CLOB-ready market found in top 50.")
        logger.info("Trying a direct fetch for a known liquid market...")
        # Fallback to a common high-volume market if top list fails
        # Market: "Who will win the 2024 Presidential Election?" (Very liquid)
        test_token_id = "21742461971155796013371363503204989052187315569477057197827453715391300070197"
        logger.info(f"Using fallback Token ID: {test_token_id}")
    else:
        logger.info(f"Targeting Market: {test_market.question}")
        logger.info(f"Token ID: {test_token_id}")

    # Place a $2 BUY order
    amount = 2.0 # $2 USDC (Polymarket min is $1)
    logger.info(f"Placing $1 test BUY order...")
    
    result = await client.place_market_order(
        token_id=test_token_id,
        side=Side.BUY,
        amount=amount
    )

    if result.success:
        logger.info(f"🚀 SUCCESS! Order placed. ID: {result.order_id}")
        logger.info(f"TX Hash: {result.transaction_hash}")
    else:
        logger.error(f"❌ FAILED: {result.error}")

if __name__ == "__main__":
    asyncio.run(test_order())
