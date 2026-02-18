import asyncio
import requests
from src.api.polymarket_client import PolymarketClient
from src.config import get_settings

async def cancel_and_liquidate():
    client = PolymarketClient()
    await client.initialize()
    
    print("EMERGENCY: CANCELING ALL ORDERS AND SELLING EVERYTHING...")
    
    # 1. Cancel all open orders
    try:
        orders = client.clob_client.get_open_orders()
        print(f"Found {len(orders)} open orders. Canceling...")
        for o in orders:
            client.clob_client.cancel_order(o.get("orderID"))
            print(f"Canceled order {o.get('orderID')}")
    except Exception as e:
        print(f"Could not cancel orders: {e}")

    # 2. Get tokens from balance/positions
    wallet = client.wallet_address
    url = f"https://data-api.polymarket.com/positions?user={wallet}"
    positions = requests.get(url).json()
    
    for p in positions:
        tid = p.get("asset") or p.get("asset_id") or p.get("tokenId")
        qty = float(p.get("size", 0))
        
        if qty < 1.0: continue
        
        print(f"Attempting to sell {qty} of {tid}")
        
        from src.api.polymarket_client import TradeOrder, Side
        order = TradeOrder(
            token_id=tid, side=Side.SELL, size=qty, price=0.01,
            market_id="", market_question=""
        )
        
        res = await client.place_order(order)
        if res.success:
            print(f"SUCCESS: Sold {tid}")
        else:
            print(f"FAILED: {tid} - {res.error}")

    print(f"Final balance: {await client.get_balance()}")

if __name__ == "__main__":
    asyncio.run(cancel_and_liquidate())
