import asyncio
import aiohttp
from datetime import datetime, timezone

async def check():
    target = "0x63ce342161250d705dc0b16df89036c8e5f9ba9a"
    url = f"https://data-api.polymarket.com/trades?user={target}&limit=5"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            trades = await response.json()
            print(f"\nTarget: {target}")
            print(f"Current UTC: {datetime.now(timezone.utc)}")
            print("-" * 50)
            for t in trades:
                ts = t.get("timestamp")
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                print(f"Time: {dt} | Side: {t.get('side')} | Market: {t.get('title')[:30]}...")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(check())
