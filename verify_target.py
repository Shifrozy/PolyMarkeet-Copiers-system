import asyncio
import logging
from datetime import datetime, timezone
from src.api.trade_monitor import TradeMonitor, TradeEvent
from src.config import get_settings

# Setup logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)8s | %(message)s"
)
logger = logging.getLogger(__name__)

async def test_monitor():
    settings = get_settings()
    target = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"
    
    logger.info("========================================")
    logger.info(f"🔍 TESTING MONITOR FOR: {target}")
    logger.info("========================================")
    
    monitor = TradeMonitor(target_wallet=target)
    
    def on_trade(event: TradeEvent):
        logger.info("----------------------------------------")
        logger.info(f"🎯 NEW TRADE DETECTED!")
        logger.info(f"⏰ Time: {event.timestamp}")
        logger.info(f"🏷️ Side: {event.side}")
        logger.info(f"💰 Price: ${event.price}")
        logger.info(f"📊 Size: {event.size}")
        logger.info(f"🔗 TX: {event.transaction_hash}")
        logger.info("----------------------------------------")

    monitor.add_callback(on_trade)
    
    await monitor.start()
    
    logger.info("📡 Monitor started. Waiting for trades...")
    logger.info("Note: Detection check happens every 1 second.")
    
    # Run for 5 minutes or until interrupted
    try:
        count = 0
        while count < 300:
            await asyncio.sleep(1)
            count += 1
            if count % 30 == 0:
                logger.info(f"⏳ Still monitoring... ({count}s elapsed)")
    except KeyboardInterrupt:
        pass
    finally:
        await monitor.stop()

if __name__ == "__main__":
    asyncio.run(test_monitor())
