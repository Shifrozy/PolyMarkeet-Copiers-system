import requests
import json
from src.config import get_settings

def sync_emergency():
    settings = get_settings()
    wallet = "0x8e3696515239e31c9B662353167f5e8655DE7F61"
    
    print(f"EMERGENCY LIQUIDATION FOR: {wallet}")
    
    # Get positions from Data API
    try:
        url = f"https://data-api.polymarket.com/positions?user={wallet}"
        r = requests.get(url)
        positions = r.json()
    except Exception as e:
        print(f"Failed to get positions: {e}")
        return

    to_close = []
    for p in positions:
        tid = p.get("asset") or p.get("asset_id") or p.get("tokenId")
        size = float(p.get("size", 0))
        if size > 1.0: # Only significant positions
            to_close.append({"token_id": tid, "size": size})
            
    if not to_close:
        print("No significant positions found.")
        return
        
    from src.api.polymarket_client import PolymarketClient, Side
    import asyncio
    
    async def close_them(items):
        client = PolymarketClient()
        await client.initialize()
        
        for item in items:
            tid = item['token_id']
            qty = item['size']
            
            # Try to get price from multiple sources
            price = None
            try:
                # 1. Try CLOB book
                res = requests.get(f"https://clob.polymarket.com/book?token_id={tid}")
                if res.status_code == 200:
                    book = res.json()
                    bids = book.get("bids", [])
                    if bids:
                        price = float(bids[0]["price"])
                
                # 2. Try Data API Price
                if price is None:
                    res = requests.get(f"https://data-api.polymarket.com/prices?token_id={tid}")
                    if res.status_code == 200:
                        p_data = res.json()
                        price = float(p_data.get("price", 0))
            except:
                pass
                
            if price is None or price <= 0:
                print(f"Could not get price for {tid}, skipping safety and trying 0.05 sell (DANGEROUS)")
                # Instead of skipping, let's try to fetch market info to get a hint
                price = 0.05 # Last resort very low sell
            
            print(f"Selling {qty} of {tid} at approx {price}...")
            # We use a slightly lower price for Sell to be a taker
            sell_price = max(0.01, price * 0.9) 
            
            from src.api.polymarket_client import TradeOrder
            order = TradeOrder(
                token_id=tid,
                side=Side.SELL,
                size=qty,
                price=sell_price, # This acts as a 'SELL AT LEAST THIS'
                market_id="",
                market_question=""
            )
            
            res = await client.place_order(order)
            if res.success:
                print(f"SUCCESS: Sold {tid} at {sell_price}")
            else:
                print(f"FAILED: {tid} - {res.error}")
                
        print(f"Final Balance: {await client.get_balance()}")

    asyncio.run(close_them(to_close))

if __name__ == "__main__":
    sync_emergency()
