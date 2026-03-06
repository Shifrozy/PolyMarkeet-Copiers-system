"""
Copy Trading Engine
==================
Core engine that handles copying trades from target wallet to user's account.
Supports time-period filtered stats and MetaMask/EOA wallet execution.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.api.polymarket_client import PolymarketClient, Side, OrderResult
from src.api.trade_monitor import TradeMonitor, TradeEvent, TradeEventType
from src.api.data_fetcher import DataFetcher, WalletStats, TimePeriod
from src.config import get_settings

logger = logging.getLogger(__name__)


class CopyMode(Enum):
    """Copy trading modes."""
    PROPORTIONAL = "proportional"  # Copy same % of portfolio
    FIXED = "fixed"                 # Copy with fixed amount
    MIRROR = "mirror"               # Exact same size


@dataclass
class CopyTradeResult:
    """Result of a copy trade operation."""
    success: bool
    original_event: TradeEvent
    copied_order: Optional[OrderResult] = None
    original_size: float = 0.0
    copied_size: float = 0.0
    original_price: float = 0.0
    copied_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None


@dataclass
class CopyStats:
    """Statistics for copy trading session."""
    total_copies: int = 0
    successful_copies: int = 0
    failed_copies: int = 0
    total_volume: float = 0.0
    total_fees: float = 0.0
    session_start: datetime = field(default_factory=datetime.now)
    copy_history: List[CopyTradeResult] = field(default_factory=list)


class CopyTradingEngine:
    """
    Main copy trading engine that:
    1. Monitors target wallet for new trades
    2. Calculates appropriate position sizes
    3. Executes copies on user's MetaMask wallet
    4. Tracks statistics and history with time-period filtering
    """
    
    def __init__(
        self,
        target_wallet: Optional[str] = None,
        mode: CopyMode = CopyMode.PROPORTIONAL,
        scale_factor: float = 1.0,
        fixed_amount: float = 10.0,
        max_amount: float = 100.0
    ):
        self.settings = get_settings()
        self.target_wallet = target_wallet or self.settings.target_wallet_address
        self.mode = mode
        self.scale_factor = scale_factor
        self.fixed_amount = fixed_amount
        self.max_amount = max_amount
        
        # Components
        self.client = PolymarketClient()
        self.monitor = TradeMonitor(self.target_wallet)
        self.data_fetcher = DataFetcher()
        
        # State
        self._is_running = False
        self._stats = CopyStats()
        self._ui_callbacks: List[Callable] = []
        self._target_stats: Optional[WalletStats] = None
        self._user_stats: Optional[WalletStats] = None
        
        # Current time period (can be changed from dashboard)
        self._current_period = self.settings.default_period or TimePeriod.ALL
        
        # ─── Risk Management State ───
        self._daily_pnl: float = 0.0          # Track daily P&L
        self._daily_reset_date: str = ""      # Date string for daily reset
        self._last_copy_time: float = 0       # For cooldown timer
        self._market_exposure: Dict[str, float] = {}  # market_id -> total $ invested
        self._risk_stopped: bool = False       # True if risk limit triggered auto-stop
        self._daily_trade_count: int = 0       # Track daily trade count
    
    @property
    def current_period(self) -> str:
        return self._current_period
    
    @current_period.setter
    def current_period(self, value: str):
        """Set the current time period and trigger a refresh."""
        if value in (TimePeriod.DAY_1, TimePeriod.MONTH_1, TimePeriod.YEAR_1, TimePeriod.ALL):
            self._current_period = value
            logger.info(f"📅 Time period changed to: {value}")
    
    async def initialize(self) -> bool:
        """Initialize all components."""
        try:
            logger.info("🚀 Initializing Copy Trading Engine...")
            
            # Initialize API client (MetaMask or Polymarket)
            if not await self.client.initialize():
                logger.warning("⚠️ Client init failed. Monitoring-only mode.")
            
            # Initialize data fetcher
            await self.data_fetcher.initialize()
            
            # Register trade callback
            self.monitor.add_callback(self._on_trade_event)
            
            wallet_type = getattr(self.settings, 'wallet_type', 'metamask')
            logger.info(f"✅ Engine initialized! Wallet: {wallet_type.upper()}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization error: {e}")
            return False
    
    async def start(self):
        """Start copy trading."""
        if self._is_running:
            logger.warning("Copy trading is already running")
            return
        
        self._is_running = True
        self._stats = CopyStats()
        
        wallet_type = getattr(self.settings, 'wallet_type', 'metamask')
        logger.info(f"""
        ╔══════════════════════════════════════════════════════╗
        ║        🤖 COPY TRADING ENGINE STARTED 🤖              ║
        ╠══════════════════════════════════════════════════════╣
        ║  Target: {self.target_wallet[:20]}...         
        ║  Mode: {self.mode.value}                         
        ║  Scale: {self.scale_factor}x                   
        ║  Max Trade: ${self.max_amount}                        
        ║  Wallet: {wallet_type.upper()}
        ║  Period: {self._current_period}
        ╚══════════════════════════════════════════════════════╝
        """)
        
        # Start monitoring
        await self.monitor.start()
        
        # Start stats refresh loop
        asyncio.create_task(self._refresh_stats_loop())
    
    async def stop(self):
        """Stop copy trading."""
        self._is_running = False
        await self.monitor.stop()
        await self.data_fetcher.close()
        
        logger.info("⏹️ Copy Trading Engine stopped")
        self._log_session_summary()
    
    async def _on_trade_event(self, event: TradeEvent):
        """Handle incoming trade event from target wallet."""
        if not self._is_running:
            return
        
        if event.event_type != TradeEventType.ORDER_FILLED:
            return
        
        # Compact log
        logger.info(f"🔔 [LIVE] {event.side} {event.size:.2f} @ {event.price:.3f} | {event.market_id[:12]}...")
        
        # ─── Risk Management Checks ───
        skip_reason = await self._check_risk_filters(event)
        if skip_reason:
            logger.info(f"🛡️ SKIP: {skip_reason}")
            self._stats.total_copies += 1
            self._stats.failed_copies += 1
            result = CopyTradeResult(
                success=False,
                original_event=event,
                original_size=event.size,
                original_price=event.price,
                error=f"Risk: {skip_reason}"
            )
            self._stats.copy_history.append(result)
            await self._notify_ui(result)
            return
        
        # Execute copy trade
        result = await self._execute_copy(event)
        
        # Update stats
        self._stats.total_copies += 1
        if result.success:
            self._stats.successful_copies += 1
            self._stats.total_volume += result.copied_size * result.copied_price
            
            # Track per-market exposure
            mkt = event.market_id
            cost = result.copied_size * result.copied_price
            self._market_exposure[mkt] = self._market_exposure.get(mkt, 0) + cost
            
            # Update last copy time for cooldown
            import time
            self._last_copy_time = time.time()
            
            # Increment daily trade counter
            self._daily_trade_count += 1
        else:
            self._stats.failed_copies += 1
        
        self._stats.copy_history.append(result)
        
        # Notify UI
        await self._notify_ui(result)
    
    async def _check_risk_filters(self, event: TradeEvent) -> Optional[str]:
        """Run all risk filters. Returns skip reason string or None if OK."""
        import time
        s = self.settings
        
        # Reset daily counters at midnight
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._daily_reset_date:
            self._daily_pnl = 0.0
            self._daily_trade_count = 0
            self._daily_reset_date = today
        
        # ─── HIGH IMPACT ───
        
        # 1. Daily Loss Limit
        if s.daily_loss_limit > 0 and self._daily_pnl <= -s.daily_loss_limit:
            self._risk_stopped = True
            return f"Daily loss limit hit (${abs(self._daily_pnl):.2f} >= ${s.daily_loss_limit:.2f})"
        
        # 2. Max Daily Trades
        if s.max_daily_trades > 0 and self._daily_trade_count >= s.max_daily_trades:
            return f"Max daily trades reached ({self._daily_trade_count}/{s.max_daily_trades})"
        
        # 2. Max Open Positions
        if s.max_open_positions > 0:
            try:
                positions = await self.client.get_positions()
                open_count = len([p for p in positions if float(p.get('size', 0)) > 0])
                if open_count >= s.max_open_positions:
                    return f"Max positions reached ({open_count}/{s.max_open_positions})"
            except Exception:
                pass  # Don't block trade if check fails
        
        # 3. Min Price Filter
        if s.min_price_filter > 0 and event.price < s.min_price_filter:
            return f"Price too low ({event.price:.3f} < {s.min_price_filter:.2f})"
        
        # 4. Max Price Filter
        if s.max_price_filter > 0 and event.price > s.max_price_filter:
            return f"Price too high ({event.price:.3f} > {s.max_price_filter:.2f})"
        
        # 5. Balance Protection
        if s.balance_protection > 0:
            try:
                balance = await self.client.get_balance()
                if balance <= s.balance_protection:
                    self._risk_stopped = True
                    return f"Balance protection (${balance:.2f} <= ${s.balance_protection:.2f})"
            except Exception:
                pass
        
        # ─── MEDIUM IMPACT ───
        
        # 6. Skip SELL copies
        if s.skip_sell_copies and event.side == "SELL":
            return "SELL trade skipped (skip_sell_copies=ON)"
        
        # 7. Cooldown Timer
        if s.cooldown_seconds > 0:
            elapsed = time.time() - self._last_copy_time
            if elapsed < s.cooldown_seconds:
                remaining = s.cooldown_seconds - elapsed
                return f"Cooldown active ({remaining:.0f}s remaining)"
        
        # 8. Per-Market Limit
        if s.per_market_limit > 0:
            current_exposure = self._market_exposure.get(event.market_id, 0)
            trade_cost = event.size * event.price
            if current_exposure + trade_cost > s.per_market_limit:
                return f"Per-market limit (${current_exposure:.2f} + ${trade_cost:.2f} > ${s.per_market_limit:.2f})"
        
        # ─── ADVANCED ───
        
        # 9. Win Rate Filter
        if s.min_target_winrate > 0 and self._target_stats:
            if self._target_stats.win_rate < s.min_target_winrate:
                return f"Target win rate too low ({self._target_stats.win_rate:.1f}% < {s.min_target_winrate:.0f}%)"
        
        # 10. Market Expiry Filter
        if s.skip_expiring_hours > 0:
            try:
                market_info = await self.data_fetcher.get_market_info(event.market_id)
                if market_info and market_info.end_date:
                    from datetime import timezone
                    hours_left = (market_info.end_date - datetime.now(timezone.utc)).total_seconds() / 3600
                    if hours_left < s.skip_expiring_hours:
                        return f"Market expiring soon ({hours_left:.0f}h < {s.skip_expiring_hours}h)"
            except Exception:
                pass
        
        return None  # All checks passed
    
    async def _execute_copy(self, event: TradeEvent) -> CopyTradeResult:
        """Execute a copy of the detected trade via MetaMask wallet."""
        try:
            copy_size = self._calculate_copy_size(event.size, event.price)
            
            if copy_size <= 0:
                return CopyTradeResult(
                    success=False,
                    original_event=event,
                    original_size=event.size,
                    original_price=event.price,
                    error="Calculated copy size is 0"
                )
            
            logger.info(f"📤 Copying via MetaMask: {copy_size:.4f} (original: {event.size:.4f})")
            
            side = Side.BUY if event.side == "BUY" else Side.SELL
            
            # Execute order through MetaMask wallet
            order_result = await self.client.place_market_order(
                token_id=event.token_id,
                side=side,
                amount=copy_size * event.price,
                market_id=event.market_id
            )
            
            if order_result.success:
                logger.info(f"✅ Copy successful! Order: {order_result.order_id}")
            else:
                logger.error(f"❌ Copy failed: {order_result.error}")
            
            return CopyTradeResult(
                success=order_result.success,
                original_event=event,
                copied_order=order_result,
                original_size=event.size,
                copied_size=copy_size,
                original_price=event.price,
                copied_price=event.price,
                error=order_result.error
            )
            
        except Exception as e:
            logger.error(f"❌ Copy execution error: {e}")
            return CopyTradeResult(
                success=False,
                original_event=event,
                original_size=event.size,
                original_price=event.price,
                error=str(e)
            )
    
    def _calculate_copy_size(self, original_size: float, price: float) -> float:
        """Calculate the size for the copy trade based on mode."""
        if self.mode == CopyMode.MIRROR:
            size = original_size
        elif self.mode == CopyMode.FIXED:
            size = self.fixed_amount / price
        elif self.mode == CopyMode.PROPORTIONAL:
            size = original_size * self.scale_factor
        else:
            size = original_size
        
        # Apply max limit
        max_size = self.max_amount / price
        size = min(size, max_size)
        
        return size
    
    async def _refresh_stats_loop(self):
        """Periodically refresh wallet statistics with current time period."""
        from eth_account import Account
        user_wallet = None
        
        if self.settings.private_key and len(self.settings.private_key) >= 64:
            try:
                pk = self.settings.private_key
                if pk.startswith("0x"): pk = pk[2:]
                user_account = Account.from_key(pk)
                user_wallet = user_account.address
                logger.info(f"👤 User wallet: {user_wallet}")
            except Exception as e:
                logger.error(f"Error deriving user wallet: {e}")
        else:
            logger.warning("⚠️ No PRIVATE_KEY in .env. User stats disabled.")

        while self._is_running:
            try:
                period = self._current_period
                logger.info(f"🔄 Refreshing [{period}]...")
                
                # Fetch target stats with current period
                self._target_stats = await self.data_fetcher.get_wallet_stats(
                    self.target_wallet,
                    period=period
                )
                await self._notify_ui_data("target_stats", self._target_stats)
                
                # Fetch user stats and balance
                if user_wallet:
                    stats_task = self.data_fetcher.get_wallet_stats(user_wallet, period=period)
                    balance_task = self.client.get_balance()
                    
                    self._user_stats, balance = await asyncio.gather(stats_task, balance_task)
                    
                    await self._notify_ui_data("user_stats", self._user_stats)
                    await self._notify_ui_data("balance_update", balance)
                
                pnl = self._target_stats.total_pnl if self._target_stats else 0
                logger.info(f"✅ Synced [{period}] | Target P&L: ${pnl:,.2f}")
                
            except Exception as e:
                logger.error(f"Refresh error: {e}")
            
            # Wait 60 seconds between refreshes (Stats don't need to be hyper-fast)
            # Trade monitoring remains fast in its own loop
            for _ in range(600):
                if not self._is_running: break
                await asyncio.sleep(0.1)

    async def _notify_ui_data(self, data_type: str, data: Any):
        """Notify UI about data updates."""
        for callback in self._ui_callbacks:
            try:
                update = (data_type, data)
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.error(f"UI data callback error: {e}")
    
    async def _notify_ui(self, result: CopyTradeResult):
        """Notify UI about copy result."""
        for callback in self._ui_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(result)
                else:
                    callback(result)
            except Exception as e:
                logger.error(f"UI callback error: {e}")
    
    def add_ui_callback(self, callback: Callable):
        """Add a callback for UI updates."""
        self._ui_callbacks.append(callback)
    
    def _log_session_summary(self):
        """Log session summary."""
        duration = datetime.now() - self._stats.session_start
        
        logger.info(f"""
        ╔══════════════════════════════════════════════════════╗
        ║              📊 SESSION SUMMARY 📊                    ║
        ╠══════════════════════════════════════════════════════╣
        ║  Duration: {duration}
        ║  Total Copies: {self._stats.total_copies}
        ║  Successful: {self._stats.successful_copies}
        ║  Failed: {self._stats.failed_copies}
        ║  Volume: ${self._stats.total_volume:.2f}
        ╚══════════════════════════════════════════════════════╝
        """)
    
    @property
    def is_running(self) -> bool:
        return self._is_running
    
    @property
    def stats(self) -> CopyStats:
        return self._stats
    
    @property
    def target_stats(self) -> Optional[WalletStats]:
        return self._target_stats
    
    @property
    def user_stats(self) -> Optional[WalletStats]:
        return self._user_stats
    
    def get_copy_history(self) -> List[CopyTradeResult]:
        return self._stats.copy_history.copy()
