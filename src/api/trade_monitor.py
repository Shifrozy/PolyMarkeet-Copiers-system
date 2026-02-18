"""
Trade Monitor
=============
Real-time monitoring of trades for a target wallet using WebSocket.
This is the core component for zero-delay copy trading.
"""

import asyncio
import json
import logging
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import websockets
import aiohttp

from src.config import get_settings

logger = logging.getLogger(__name__)


class TradeEventType(Enum):
    """Types of trade events."""
    NEW_ORDER = "new_order"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    POSITION_CHANGE = "position_change"


@dataclass
class TradeEvent:
    """Represents a real-time trade event."""
    event_type: TradeEventType
    wallet_address: str
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    timestamp: datetime
    order_id: Optional[str] = None
    transaction_hash: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None


class TradeMonitor:
    """
    Real-time trade monitor using WebSocket connection.
    Monitors a target wallet and triggers callbacks when trades occur.
    """
    
    # Polymarket WebSocket endpoints
    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"
    
    def __init__(self, target_wallet: Optional[str] = None):
        """
        Initialize the trade monitor.
        
        Args:
            target_wallet: Wallet address to monitor (defaults to config value).
        """
        self.settings = get_settings()
        self.target_wallet = target_wallet or self.settings.target_wallet_address
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._is_running = False
        self._callbacks: List[Callable[[TradeEvent], None]] = []
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
        self._last_events: List[TradeEvent] = []
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._session: Optional[aiohttp.ClientSession] = None
        self._seen_tx_hashes = set()
    
    def add_callback(self, callback: Callable[[TradeEvent], None]):
        """
        Add a callback function to be called when a trade event occurs.
        
        Args:
            callback: Function that takes a TradeEvent as argument.
        """
        self._callbacks.append(callback)
        logger.info(f"Added trade callback. Total callbacks: {len(self._callbacks)}")
    
    def remove_callback(self, callback: Callable[[TradeEvent], None]):
        """Remove a callback function."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    async def start(self):
        """Start monitoring for trades."""
        if self._is_running:
            logger.warning("Trade monitor is already running")
            return
        
        self._is_running = True
        logger.info(f"🔄 Starting trade monitor for wallet: {self.target_wallet}")
        
        # Initialize persistent session
        if not self._session or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            
        asyncio.create_task(self._polling_loop())
    
    async def stop(self):
        """Stop monitoring for trades."""
        self._is_running = False
        logger.info("⏹️ Trade monitor stopped")
    
    async def _polling_loop(self):
        """High-frequency polling loop for trade detection."""
        check_interval = 1.0  # seconds
        
        # Pre-fill seen hashes with most recent trades to avoid duplicating history
        try:
            url = f"{self.settings.data_api_url}/trades"
            async with self._session.get(url, params={"user": self.target_wallet.lower(), "limit": 50}) as res:
                if res.status == 200:
                    data = await res.json()
                    for t in data:
                        tx = t.get("transactionHash")
                        if tx: self._seen_tx_hashes.add(tx)
            logger.info(f"✅ Pre-filled {len(self._seen_tx_hashes)} existing trades to avoid duplicates.")
        except Exception as e:
            logger.error(f"Failed to pre-fill trades: {e}")

        # Start time for filtering - ONLY process trades after this
        start_time = datetime.now(timezone.utc)
        logger.info(f"🚀 Monitor started at {start_time}. Ignoring all trades before this.")

        while self._is_running:
            try:
                url = f"{self.settings.data_api_url}/trades"
                # Check both roles
                for role in ["user", "maker"]:
                    params = {role: self.target_wallet.lower(), "limit": 10}
                    async with self._session.get(url, params=params) as response:
                        if response.status != 200: continue
                        trades = await response.json()
                        if not isinstance(trades, list): continue
                        
                        for trade in reversed(trades):
                            tx_hash = trade.get("transactionHash")
                            if not tx_hash or tx_hash in self._seen_tx_hashes:
                                continue
                                
                            # Parse trade time
                            ts = trade.get("timestamp")
                            trade_time = datetime.now(timezone.utc)
                            try:
                                if isinstance(ts, (int, float)):
                                    trade_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                                else:
                                    ts_str = str(ts).replace('Z', '+00:00')
                                    trade_time = datetime.fromisoformat(ts_str)
                                    if trade_time.tzinfo is None:
                                        trade_time = trade_time.replace(tzinfo=timezone.utc)
                            except: pass

                            # STRICT FILTER: Must be newer than start_time
                            if trade_time <= start_time:
                                self._seen_tx_hashes.add(tx_hash) # Mark as seen so we don't check timestamp again
                                continue

                            # Final double check before firing
                            if tx_hash in self._seen_tx_hashes: continue
                            
                            logger.info(f"✨ LIVE TRADE DETECTED: {tx_hash[:12]}... at {trade_time}")
                            
                            token_id = trade.get("asset") or trade.get("asset_id") or ""
                            market_id = trade.get("conditionId") or trade.get("market") or ""
                            
                            event = TradeEvent(
                                event_type=TradeEventType.ORDER_FILLED,
                                wallet_address=self.target_wallet,
                                market_id=market_id,
                                token_id=token_id,
                                side=trade.get("side", "").upper(),
                                price=float(trade.get("price", 0)),
                                size=float(trade.get("size", 0)),
                                timestamp=trade_time,
                                transaction_hash=tx_hash,
                                raw_data=trade
                            )
                            
                            self._seen_tx_hashes.add(tx_hash)
                            await self._trigger_callbacks(event)
                            self._last_events.append(event)
                            if len(self._last_events) > 100: self._last_events.pop(0)

                # Prevent API spam
                await asyncio.sleep(1.0)
                
                if len(self._seen_tx_hashes) > 10000:
                    self._seen_tx_hashes = set(list(self._seen_tx_hashes)[-5000:])
                
            except Exception as e:
                logger.error(f"Detection polling error: {e}")
            
            await asyncio.sleep(check_interval)

    async def _trigger_callbacks(self, event: TradeEvent):
        """Trigger all registered callbacks for a trade event."""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def _is_duplicate_event(self, event: TradeEvent) -> bool:
        """Check if an event is a duplicate of a recent event."""
        for e in self._last_events[-20:]:
            if (e.transaction_hash and 
                e.transaction_hash == event.transaction_hash):
                return True
            if (e.order_id and e.order_id == event.order_id and 
                e.event_type == event.event_type):
                return True
        return False
    
    @property
    def is_running(self) -> bool:
        """Check if monitor is currently running."""
        return self._is_running
    
    @property
    def last_events(self) -> List[TradeEvent]:
        """Get list of recent events."""
        return self._last_events.copy()
    
    def get_event_count(self) -> int:
        """Get total number of events received."""
        return len(self._last_events)
