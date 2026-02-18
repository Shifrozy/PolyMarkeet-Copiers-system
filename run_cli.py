"""
Terminal Copy Trading Runner
===========================
Starts the bot in CLI mode to debug why trades aren't being copied.
"""
import asyncio
import sys
import os
import logging
from colorlog import ColoredFormatter

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.engine.copy_engine import CopyTradingEngine
from src.config import get_settings

def setup_logging():
    """Setup beautiful colored logging for terminal."""
    formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s%(reset)s",
        datefmt="%H:%M:%S",
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    # Silence noisy logs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("pydantic").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

async def run_cli():
    setup_logging()
    settings = get_settings()
    
    print("\n" + "="*60)
    print("  POLYMARKET COPY TRADING BOT - CLI MODE")
    print("="*60 + "\n")
    
    engine = CopyTradingEngine()
    
    # Target info
    print(f"Target Wallet: {settings.target_wallet_address}")
    print(f"Your Wallet:   (Deriving...)")
    print(f"Copy Mode:     {settings.copy_mode}")
    print(f"Scale Factor:  {settings.scale_factor}x")
    print("-" * 60)
    
    # Initialize Engine
    print("Initializing bot engine...")
    success = await engine.initialize()
    if not success:
        print("\n[!] FATAL: Bot failed to initialize. Check if your PRIVATE_KEY is correct.")
        return
        
    if not engine.client.clob_client:
        print("\n[!] WARNING: Bot is in MONITORING-ONLY mode (No API Keys Derived).")
        print("    Trades will be DETECTED but NOT COPIED.")
        print("    To fix this, you MUST get API credentials from Polymarket and add to .env")
        print("-" * 60)
    
    # Start Engine
    print("Starting monitoring loop...")
    await engine.start()
    
    try:
        print("\nBOT IS RUNNING. Press Ctrl+C to stop.\n")
        while True:
            # Show stats if available
            stats = engine.target_stats
            if stats:
                print(f"Stats Update: {len(stats.trade_history)} trades, Target P&L: ${stats.total_pnl:.2f}")
            else:
                print("Stats Update: Loading...")
            await asyncio.sleep(30)
    except KeyboardInterrupt:
        print("\nStopping bot...")
        await engine.stop()
        print("Bot stopped safely.")

if __name__ == "__main__":
    asyncio.run(run_cli())
