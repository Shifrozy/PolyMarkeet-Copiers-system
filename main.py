"""
Polymarket Copy Trading Bot
===========================
Main entry point for the application.

Usage:
    python main.py           - Run with GUI dashboard
    python main.py --cli     - Run in CLI mode (no GUI)
    python main.py --help    - Show help
"""

import sys
import asyncio
import argparse
import logging
from colorlog import ColoredFormatter

from src.config import settings, validate_settings
from src.gui.main_dashboard import run_dashboard
from src.engine.copy_engine import CopyTradingEngine, CopyMode


def setup_logging(verbose: bool = False):
    """Setup colored logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s | %(levelname)-8s%(reset)s | "
        "%(cyan)s%(name)s%(reset)s | %(message)s",
        datefmt="%H:%M:%S",
        log_colors={
            'DEBUG': 'white',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )
    
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)


def print_banner():
    """Print application banner."""
    banner = """
    ╔══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║   🤖  POLYMARKET COPY TRADING BOT  🤖                            ║
    ║                                                                   ║
    ║   Copy trades from any wallet with zero delay!                   ║
    ║   Professional dashboard with time filters (1D/1M/1Y/ALL)        ║
    ║   MetaMask & Polymarket wallet support                           ║
    ║                                                                   ║
    ║   Version: 2.0.0                                                  ║
    ║   Author: Polymarket Bot Developer                               ║
    ║                                                                   ║
    ╚══════════════════════════════════════════════════════════════════╝
    """
    print(banner)


async def run_cli():
    """Run the bot in CLI mode without GUI."""
    print_banner()
    
    # Validate settings
    is_valid, errors = validate_settings()
    if not is_valid:
        print("\n❌ Configuration errors:")
        for error in errors:
            print(f"   • {error}")
        print("\nPlease configure .env file with your credentials.")
        return
    
    wallet_type = getattr(settings, 'wallet_type', 'metamask')
    wallet_icon = "🦊" if wallet_type == "metamask" else "🏦"
    print(f"\n{wallet_icon} Wallet Mode: {wallet_type.upper()}")
    print(f"📍 Target Wallet: {settings.target_wallet_address}")
    print(f"📊 Copy Mode: {settings.copy_mode}")
    print(f"📈 Scale Factor: {settings.scale_factor}x")
    print(f"💰 Max Trade: ${settings.max_trade_amount}")
    
    # Create engine
    engine = CopyTradingEngine(
        target_wallet=settings.target_wallet_address,
        mode=CopyMode(settings.copy_mode),
        scale_factor=settings.scale_factor,
        fixed_amount=settings.fixed_trade_amount,
        max_amount=settings.max_trade_amount
    )
    
    # Add console callback
    def on_copy(result):
        status = "✅ SUCCESS" if result.success else "❌ FAILED"
        print(f"\n{status} | {result.original_event.side} {result.copied_size:.4f} @ ${result.copied_price:.3f}")
    
    engine.add_ui_callback(on_copy)
    
    # Initialize and start
    print("\n🚀 Initializing...")
    if not await engine.initialize():
        print("❌ Failed to initialize. Check your API credentials.")
        return
    
    print("✅ Initialized successfully!")
    print("\n👀 Monitoring for trades... (Press Ctrl+C to stop)\n")
    
    try:
        await engine.start()
        
        # Keep running
        while engine.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Stopping...")
        await engine.stop()
        print("👋 Goodbye!")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Polymarket Copy Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              Run with GUI dashboard
  python main.py --cli        Run in CLI mode
  python main.py -v           Run with verbose logging
        """
    )
    
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in CLI mode without GUI"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    if args.cli:
        # Run in CLI mode
        asyncio.run(run_cli())
    else:
        # Run GUI dashboard
        print_banner()
        run_dashboard()


if __name__ == "__main__":
    main()
