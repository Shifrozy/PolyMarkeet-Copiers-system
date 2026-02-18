import asyncio
import requests
import logging
from src.api.polymarket_client import PolymarketClient, Side
from src.config import get_settings

def log(msg):
    print(msg)

async def final_liquidation():
    client = PolymarketClient()
    await client.initialize()
    
    wallet = client.wallet_address
    log(f"STARTING FINAL EMERGENCY FOR: {wallet}")

    # 1. Cancel ALL pending orders 
    try:
        resp = requests.get(f"https://clob.polymarket.com/orders-open?user={wallet}")
        if resp.status_code == 200:
            open_orders = resp.json()
            log(f"Found {len(open_orders)} open orders. Canceling...")
            for o in open_orders:
                oid = o.get("orderID")
                client.clob_client.cancel_order(oid)
                log(f"Canceled {oid}")
    except Exception as e:
        log(f"Cancel error: {e}")

    # 2. Discover positions 
    assets = {} # tid -> qty
    
    # Check Data API
    try:
        r = requests.get(f"https://data-api.polymarket.com/positions?user={wallet}")
        for p in r.json():
            tid = p.get("asset") or p.get("asset_id") or p.get("tokenId")
            size = float(p.get("size", 0))
            if size > 0.1:
                assets[tid] = size
    except: pass

    if not assets:
        log("No significant positions found to sell.")
        return

    log(f"Total Unique Assets Found: {len(assets)}")

    for tid, qty in assets.items():
        log(f"--- Processing Token: {tid} (Qty: {qty}) ---")
        
        # Get BEST BID Price
        price = 0.0
        try:
            res = requests.get(f"https://clob.polymarket.com/book?token_id={tid}")
            if res.status_code == 200:
                book = res.json()
                bids = book.get("bids", [])
                if bids:
                    price = float(bids[0]["price"])
        except: pass

        if price <= 0:
            log(f"No bids found for {tid}. Fallback 0.01.")
            price = 0.01
        
        sell_price = max(0.01, price * 0.9)
        log(f"Executing Market SELL at {sell_price}...")
        
        try:
            from py_clob_client.clob_types import OrderArgs
            order_args = OrderArgs(
                token_id=tid,
                price=round(sell_price, 2),
                size=round(qty, 2),
                side="SELL",
                fee_rate_bps=0
            )
            
            signed_order = client.clob_client.create_order(order_args)
            from py_clob_client.clob_types import OrderType
            resp = client.clob_client.post_order(signed_order, OrderType.GTC)
            
            if resp.get("success"):
                log(f"SUCCESS! Liquidated {tid}. ID: {resp.get('orderID')}")
            else:
                log(f"FAIL: {resp.get('errorMsg')}")
        except Exception as e:
            log(f"EXECUTION ERROR: {e}")

    final_bal = await client.get_balance()
    log(f"FINAL USDC BALANCE: {final_bal}")

if __name__ == "__main__":
    asyncio.run(final_liquidation())
