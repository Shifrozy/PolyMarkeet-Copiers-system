import asyncio
from src.api.polymarket_client import PolymarketClient

async def check():
    c = PolymarketClient()
    await c.initialize()
    b = await c.get_balance()
    print(f"CURRENT_BALANCE: {b}")

if __name__ == "__main__":
    asyncio.run(check())
