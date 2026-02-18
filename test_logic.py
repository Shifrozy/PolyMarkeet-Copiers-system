"""
Bot Logic Tester (Terminal Mode)
==============================
This script tests the core copy trading logic step-by-step:
1. Initialization & Authentication
2. Target wallet trade detection
3. Order placement dry-run
"""
import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.polymarket_client import PolymarketClient
from src.api.data_fetcher import DataFetcher
from src.config import get_settings

# Configure logging to see everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BotTester")

async def test_bot():
    settings = get_settings()
    logger.info("--- STARTING BOT LOGIC TEST ---")
    logger.info(f"Target Wallet: {settings.target_wallet_address}")
    
    # 1. Initialize Client
    client = PolymarketClient()
    logger.info("Initializing PolymarketClient...")
    
    # We want to see the actual error if it fails
    try:
        success = await client.initialize()
        if not success:
            logger.error("Failed to initialize PolymarketClient.")
            return
        logger.info("✅ PolymarketClient initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Error during initialization: {e}")
        return

    # 2. Check Balance
    balance = await client.get_balance()
    logger.info(f"Your USDC Balance: ${balance:.2f}")
    
    matic = await client.get_matic_balance()
    logger.info(f"Your MATIC Balance: {matic:.4f} POL")
    
    if balance < 1.0:
        logger.warning("Insufficient USDC balance for trading tests.")

    # 3. Check Target Wallet Activity
    fetcher = DataFetcher()
    await fetcher.initialize()
    logger.info(f"Fetching recent trades for target: {settings.target_wallet_address}")
    
    trades = await fetcher.get_wallet_trades(settings.target_wallet_address)
    if not trades:
        logger.warning("No recent trades found for the target wallet.")
        logger.info("If the target hasn't traded in a while, the bot will stay idle.")
    else:
        logger.info(f"✅ Found {len(trades)} recent trades for target.")
        for i, trade in enumerate(trades[:3]):
            logger.info(f"  Trade {i+1}: {trade.side} {trade.amount} @ ${trade.price} on token {trade.token_id[:10]}...")

    # 4. Simulation of Order Placement (Optional/Dry)
    # We won't place a real order yet to save funds, but we'll check if the client is ready
    if client.clob_client:
        logger.info("✅ CLOB Client is ready for order placement.")
    else:
        logger.error("❌ CLOB Client is NOT ready. Order placement will fail.")

    logger.info("--- TEST COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(test_bot())
