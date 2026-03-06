"""
Main Dashboard
=============
Professional dashboard for the Polymarket Copy Trading Bot.
Features time-period filtering (1D, 1M, 1Y, ALL) and MetaMask wallet support.
"""

import asyncio
import threading
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from queue import Queue

import customtkinter as ctk

from .theme import COLORS, FONTS, SPACING, RADIUS, get_pnl_color, format_pnl, format_percentage
from .components import (
    GlassCard, StatCard, TradeHistoryTable, StatusIndicator,
    ActionButton, PnLDisplay, PositionRow, TerminalConsole
)
from src.engine.copy_engine import CopyTradingEngine, CopyMode, CopyTradeResult
from src.api.data_fetcher import WalletStats, PositionInfo, TimePeriod
from src.config import get_settings

logger = logging.getLogger(__name__)


class TimePeriodSelector(ctk.CTkFrame):
    """
    A sleek segmented button bar for time period selection.
    Shows 1D | 1M | 1Y | ALL with active state highlighting.
    """
    
    PERIODS = [
        ("1D", TimePeriod.DAY_1),
        ("1M", TimePeriod.MONTH_1),
        ("1Y", TimePeriod.YEAR_1),
        ("ALL", TimePeriod.ALL),
    ]
    
    def __init__(self, parent, on_change=None, default="ALL", **kwargs):
        super().__init__(parent, fg_color=COLORS["bg_tertiary"], corner_radius=RADIUS["md"], **kwargs)
        
        self._on_change = on_change
        self._current = default
        self._buttons: Dict[str, ctk.CTkButton] = {}
        
        for label, value in self.PERIODS:
            btn = ctk.CTkButton(
                self,
                text=label,
                width=52,
                height=32,
                corner_radius=RADIUS["sm"],
                font=FONTS["body_bold"],
                fg_color="transparent",
                hover_color=COLORS["bg_secondary"],
                text_color=COLORS["text_muted"],
                command=lambda v=value, l=label: self._select(v, l)
            )
            btn.pack(side="left", padx=2, pady=2)
            self._buttons[value] = btn
        
        # Set initial active
        self._highlight(default)
    
    def _select(self, value: str, label: str):
        """Handle period selection."""
        self._current = value
        self._highlight(value)
        if self._on_change:
            self._on_change(value)
    
    def _highlight(self, active_value: str):
        """Highlight the active button."""
        for value, btn in self._buttons.items():
            if value == active_value:
                btn.configure(
                    fg_color=COLORS["accent_primary"],
                    text_color=COLORS["bg_dark"]
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=COLORS["text_muted"]
                )
    
    @property
    def current_period(self) -> str:
        return self._current


class LogQueueHandler(logging.Handler):
    """Logging handler that redirects logs to the UI queue."""
    def __init__(self, queue: Queue):
        super().__init__()
        self.queue = queue
        
    def emit(self, record):
        try:
            msg = self.format(record)
            self.queue.put(("log", msg, record.levelname))
        except Exception:
            self.handleError(record)


class Dashboard(ctk.CTk):
    """
    Main dashboard window for the Polymarket Copy Trading Bot.
    Features:
    - Time period filters (1D, 1M, 1Y, ALL)
    - Target wallet P&L and positions
    - User account P&L and positions  
    - Live copy trading log
    - MetaMask wallet support indicator
    """
    
    def __init__(self):
        super().__init__()
        
        # Configure window
        # Configure window
        self.title("🚀 PolyBot - Copy Trader")
        self.geometry("1200x900")
        self.minsize(900, 600)
        self.resizable(True, True)
        
        # Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=COLORS["bg_dark"])
        
        # Engine and settings
        self.settings = get_settings()
        self.engine: Optional[CopyTradingEngine] = None
        self._update_queue: Queue = Queue()
        self._current_period = self.settings.default_period or "ALL"
        
        # Row tracking to prevent flickering
        self._position_rows: Dict[str, Dict[str, PositionRow]] = {
            "target": {},
            "user": {}
        }
        self._redeemable_positions = []
        
        # Build UI
        self._create_layout()
        
        # Setup Logger Redirection
        self._setup_logging()
        
        # Start UI update loop
        self.after(50, self._process_updates)
        
        # Immediate logs for feedback
        logger.info("========================================")
        logger.info("🔥 POL YBOT - TERMINAL INITIALIZED")
        logger.info(f"⏰ System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"🎯 Target Wallet: {self.settings.target_wallet_address}")
        logger.info("========================================")
        
        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_layout(self):
        """Create the main layout."""
        # Header (Top)
        self._create_header()
        
        # Bottom panel - Activity Log (Bottom)
        # We pack this before content so it reserves its space at the bottom
        bottom_panel = self._create_bottom_panel()
        bottom_panel.pack(side="bottom", fill="x", padx=SPACING["lg"], pady=(0, SPACING["lg"]))
        
        # Main content area (Middle - Fills remaining space)
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="top", fill="both", expand=True, padx=SPACING["lg"], pady=(0, SPACING["md"]))
        
        # Left panel - Target Wallet
        left_panel = self._create_left_panel(content)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, SPACING["md"]))
        
        # Right panel - Your Account
        right_panel = self._create_right_panel(content)
        right_panel.pack(side="right", fill="both", expand=True)
    
    def _create_header(self):
        """Create the header section with time period selector."""
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"])
        header.pack(fill="x", padx=SPACING["md"], pady=(SPACING["md"], SPACING["sm"]))
        
        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=SPACING["sm"])
        
        # Left - Logo and title (compact)
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="y")
        
        title = ctk.CTkLabel(
            left,
            text="🤖 PolyBot",
            font=FONTS["subheading"],
            text_color=COLORS["text_primary"]
        )
        title.pack(side="left", pady=SPACING["sm"])
        
        # Wallet type badge
        wallet_type = getattr(self.settings, 'wallet_type', 'metamask')
        badge_text = "🦊" if wallet_type == "metamask" else "🏦"
        badge_color = COLORS["chart_orange"] if wallet_type == "metamask" else COLORS["accent_primary"]
        
        wallet_badge = ctk.CTkLabel(
            left,
            text=badge_text,
            font=FONTS["small"],
            text_color=badge_color,
            fg_color=COLORS["bg_tertiary"],
            corner_radius=RADIUS["sm"],
            padx=4, pady=2
        )
        wallet_badge.pack(side="left", padx=SPACING["xs"], pady=SPACING["sm"])
        
        # Center - Time Period Selector + Status (no expand, take only needed space)
        center = ctk.CTkFrame(inner, fg_color="transparent")
        center.pack(side="left", fill="y", expand=True, padx=SPACING["sm"])
        
        # Time period selector (1D | 1M | 1Y | ALL)
        self.period_selector = TimePeriodSelector(
            center,
            on_change=self._on_period_change,
            default=self._current_period
        )
        self.period_selector.pack(side="left", pady=SPACING["sm"])
        
        # Status indicators
        self.status_indicator = StatusIndicator(center, label="Bot", status="Offline")
        self.status_indicator.pack(side="left", padx=SPACING["sm"], pady=SPACING["sm"])
        
        self.connection_indicator = StatusIndicator(center, label="API", status="Disconnected")
        self.connection_indicator.pack(side="left", pady=SPACING["sm"])
        
        # Right - Action buttons (compact, always visible)
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right", fill="y")
        
        self.start_btn = ctk.CTkButton(
            right, text="▶ Start",
            fg_color="#00C853", hover_color="#00A844", text_color="#FFFFFF",
            font=FONTS["body_bold"], corner_radius=RADIUS["md"],
            height=36, width=80, command=self._on_start
        )
        self.start_btn.pack(side="left", padx=(0, 4), pady=SPACING["sm"])
        
        self.stop_btn = ctk.CTkButton(
            right, text="⏹ Stop",
            fg_color="#E53935", hover_color="#C62828", text_color="#FFFFFF",
            font=FONTS["body_bold"], corner_radius=RADIUS["md"],
            height=36, width=75, command=self._on_stop
        )
        self.stop_btn.pack(side="left", padx=(0, 4), pady=SPACING["sm"])
        self.stop_btn.configure(state="disabled")
        
        self.redeem_btn = ctk.CTkButton(
            right, text="🎁 Redeem",
            fg_color="#00BFA5", hover_color="#00897B", text_color="#FFFFFF",
            font=FONTS["body_bold"], corner_radius=RADIUS["md"],
            height=36, width=90, command=self._on_redeem_all
        )
        self.redeem_btn.pack(side="left", padx=(0, 4), pady=SPACING["sm"])
        
        settings_btn = ctk.CTkButton(
            right, text="⚙️",
            fg_color=COLORS["bg_tertiary"], hover_color=COLORS["border"], text_color="#FFFFFF",
            font=FONTS["body_bold"], corner_radius=RADIUS["md"],
            height=36, width=40, command=self._on_settings
        )
        settings_btn.pack(side="left", pady=SPACING["sm"])
    
    def _create_left_panel(self, parent) -> ctk.CTkFrame:
        """Create the left panel for target wallet info."""
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        
        # Panel title with wallet address
        title_frame = ctk.CTkFrame(panel, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, SPACING["sm"]))
        
        ctk.CTkLabel(
            title_frame,
            text="🎯 Target Wallet",
            font=FONTS["subheading"],
            text_color=COLORS["text_primary"]
        ).pack(side="left")
        
        # Full wallet address (clickable to copy)
        self.target_address_label = ctk.CTkLabel(
            title_frame,
            text=self.settings.target_wallet_address,
            font=FONTS["mono_small"],
            text_color=COLORS["accent_primary"],
            cursor="hand2"
        )
        self.target_address_label.pack(side="right")
        self.target_address_label.bind(
            "<Button-1>",
            lambda e: self.clipboard_clear() or self.clipboard_append(self.settings.target_wallet_address)
        )
        
        # Period indicator label
        self.target_period_label = ctk.CTkLabel(
            panel,
            text=f"📅 Showing: {self._current_period}",
            font=FONTS["small"],
            text_color=COLORS["text_muted"]
        )
        self.target_period_label.pack(anchor="w", pady=(0, SPACING["sm"]))
        
        # P&L Card
        self.target_pnl = PnLDisplay(panel, label="Target P&L")
        self.target_pnl.pack(fill="x", pady=(0, SPACING["md"]))
        
        # Stats row
        stats_frame = ctk.CTkFrame(panel, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, SPACING["md"]))
        
        self.target_trades_stat = StatCard(stats_frame, label="Total Trades", value="0", icon="📊")
        self.target_trades_stat.pack(side="left", fill="x", expand=True, padx=(0, SPACING["sm"]))
        
        self.target_volume_stat = StatCard(stats_frame, label="Total Volume", value="$0", icon="💰")
        self.target_volume_stat.pack(side="left", fill="x", expand=True, padx=(0, SPACING["sm"]))
        
        self.target_winrate_stat = StatCard(
            stats_frame, label="Win Rate", value="0%", icon="🎯",
            value_color=COLORS["success"]
        )
        self.target_winrate_stat.pack(side="left", fill="x", expand=True)
        
        # Positions section
        positions_card = GlassCard(panel, title="Active Positions")
        positions_card.pack(fill="both", expand=True)
        
        self.target_positions_container = ctk.CTkScrollableFrame(
            positions_card, fg_color="transparent"
        )
        self.target_positions_container.pack(
            fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"]
        )
        
        return panel
    
    def _create_right_panel(self, parent) -> ctk.CTkFrame:
        """Create the right panel for user account info."""
        panel = ctk.CTkFrame(parent, fg_color="transparent")
        
        # Panel title
        title_frame = ctk.CTkFrame(panel, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, SPACING["sm"]))
        
        wallet_type = getattr(self.settings, 'wallet_type', 'metamask')
        icon = "🦊" if wallet_type == "metamask" else "👤"
        label = "MetaMask Account" if wallet_type == "metamask" else "Your Account"
        
        ctk.CTkLabel(
            title_frame,
            text=f"{icon} {label}",
            font=FONTS["subheading"],
            text_color=COLORS["text_primary"]
        ).pack(side="left")
        
        # Balance display
        self.balance_label = ctk.CTkLabel(
            title_frame,
            text="Balance: $0.00",
            font=FONTS["body_bold"],
            text_color=COLORS["success"]
        )
        self.balance_label.pack(side="right")
        
        # P&L Card
        self.user_pnl = PnLDisplay(panel, label="Your P&L")
        self.user_pnl.pack(fill="x", pady=(0, SPACING["md"]))
        
        # Stats row
        stats_frame = ctk.CTkFrame(panel, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, SPACING["md"]))
        
        self.user_copies_stat = StatCard(stats_frame, label="Copied Trades", value="0", icon="📋")
        self.user_copies_stat.pack(side="left", fill="x", expand=True, padx=(0, SPACING["sm"]))
        
        self.user_success_stat = StatCard(
            stats_frame, label="Success Rate", value="0%", icon="✅",
            value_color=COLORS["success"]
        )
        self.user_success_stat.pack(side="left", fill="x", expand=True, padx=(0, SPACING["sm"]))
        
        self.user_volume_stat = StatCard(stats_frame, label="Copy Volume", value="$0", icon="💵")
        self.user_volume_stat.pack(side="left", fill="x", expand=True, padx=(0, SPACING["sm"]))
        
        self.user_redeem_stat = StatCard(
            stats_frame, label="Redeemable", value="$0.00", icon="💎",
            value_color=COLORS["chart_green"]
        )
        self.user_redeem_stat.pack(side="left", fill="x", expand=True)
        
        # Positions section
        positions_card = GlassCard(panel, title="Your Positions")
        positions_card.pack(fill="both", expand=True)
        
        self.user_positions_container = ctk.CTkScrollableFrame(
            positions_card, fg_color="transparent"
        )
        self.user_positions_container.pack(
            fill="both", expand=True, padx=SPACING["md"], pady=SPACING["md"]
        )
        
        return panel
    
    def _create_bottom_panel(self) -> ctk.CTkFrame:
        """Create the bottom panel with tabs for Log and History."""
        panel = GlassCard(self, height=240)  # Reduced height for better dashboard visibility
        panel.pack_propagate(False)
        
        # TabView for Console vs History
        self.log_tabs = ctk.CTkTabview(
            panel,
            fg_color="transparent",
            segmented_button_fg_color=COLORS["bg_tertiary"],
            segmented_button_selected_color=COLORS["accent_primary"],
            segmented_button_selected_hover_color=COLORS["accent_secondary"],
            segmented_button_unselected_hover_color=COLORS["bg_secondary"],
            text_color=COLORS["text_primary"]
        )
        self.log_tabs.pack(fill="both", expand=True, padx=SPACING["sm"], pady=SPACING["sm"])
        
        # Console Tab (Real Terminal)
        self.log_tabs.add("📟 Terminal Console")
        self.terminal = TerminalConsole(self.log_tabs.tab("📟 Terminal Console"))
        self.terminal.pack(fill="both", expand=True)
        
        # History Tab (Trade Table)
        self.log_tabs.add("📜 Copy History")
        self.trade_table = TradeHistoryTable(self.log_tabs.tab("📜 Copy History"))
        self.trade_table.pack(fill="both", expand=True)
        
        # Initial log
        self.terminal.log("Dashboard initialized. Waiting for bot start...", "INFO")
        
        return panel

    def _setup_logging(self):
        """Hook into system logging."""
        root = logging.getLogger()
        # Remove any existing handlers to avoid duplicates
        for handler in root.handlers[:]:
            root.removeHandler(handler)
            
        root.setLevel(logging.INFO)
        
        handler = LogQueueHandler(self._update_queue)
        handler.setFormatter(logging.Formatter('%(message)s'))
        root.addHandler(handler)
        
        # Don't add to module logger separately if propagation is on, 
        # or disable propagation for cleaner control.
        logger.propagate = True
        logger.setLevel(logging.INFO)
    
    # ─── Period Change Handler ──────────────────────────────────────────────
    def _on_period_change(self, period: str):
        """Handle time period change from the selector."""
        self._current_period = period
        logger.info(f"📅 Dashboard period changed to: {period}")
        
        # Update the period indicator
        period_labels = {
            TimePeriod.DAY_1: "Last 24 Hours",
            TimePeriod.MONTH_1: "Last 30 Days",
            TimePeriod.YEAR_1: "Last 365 Days",
            TimePeriod.ALL: "All Time"
        }
        self.target_period_label.configure(text=f"📅 Showing: {period_labels.get(period, period)}")
        
        # Update engine's period if running
        if self.engine and self.engine.is_running:
            self.engine.current_period = period
            # Force immediate refresh
            self._update_queue.put(("force_refresh", period))
    
    # ─── Engine Control ─────────────────────────────────────────────────────
    def _on_start(self):
        """Handle start button click."""
        logger.info("Starting copy trading bot...")
        
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_indicator.set_status("Starting...", online=False)
        
        def run_engine():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                self.engine = CopyTradingEngine(
                    target_wallet=self.settings.target_wallet_address,
                    mode=CopyMode.PROPORTIONAL,
                    scale_factor=self.settings.scale_factor,
                    fixed_amount=self.settings.fixed_trade_amount,
                    max_amount=self.settings.max_trade_amount
                )
                
                # Set current period from dashboard
                self.engine.current_period = self._current_period
                
                self.engine.add_ui_callback(self._on_copy_event)
                
                loop.run_until_complete(self.engine.initialize())
                
                self._update_queue.put(("status", "Running", True))
                self._update_queue.put(("connection", "Connected", True))
                
                loop.run_until_complete(self.engine.start())
                
                while self.engine and self.engine.is_running:
                    loop.run_until_complete(asyncio.sleep(1))
                    
            except Exception as e:
                logger.error(f"Engine error: {e}")
                self._update_queue.put(("status", f"Error: {e}", False))
            finally:
                loop.close()
        
        self._engine_thread = threading.Thread(target=run_engine, daemon=True)
        self._engine_thread.start()
    
    def _on_stop(self):
        """Handle stop button click."""
        logger.info("Stopping copy trading bot...")
        
        if self.engine:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self.engine.stop())
            self.engine = None
        
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_indicator.set_status("Stopped", online=False)
        self.connection_indicator.set_status("Disconnected", online=False)
    
    def _on_settings(self):
        """Handle settings button click."""
        self._show_settings_dialog()
    
    def _on_redeem_all(self):
        """Handle redeem all button click."""
        if not self._redeemable_positions:
            logger.info("ℹ️ No redeemable positions found.")
            return
        
        self.redeem_btn.configure(state="disabled", text="⏳ Redeeming...")
        positions_to_redeem = list(self._redeemable_positions)
        
        logger.info(f"🎁 Starting redemption of {len(positions_to_redeem)} positions...")
        
        def run_redeem():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                from src.api.polymarket_client import PolymarketClient
                client = PolymarketClient()
                loop.run_until_complete(client.initialize())
                
                balance_before = loop.run_until_complete(client.get_balance())
                success = 0
                failed = 0
                
                for pos in positions_to_redeem:
                    condition_id = pos.market_id
                    logger.info(f"🔄 Redeeming: {pos.market_question[:40]}... ({pos.size:.1f} shares)")
                    
                    result = loop.run_until_complete(client.redeem_position(condition_id))
                    
                    if result.get("success"):
                        logger.info(f"✅ Redeemed! TX: {result['tx_hash'][:16]}...")
                        success += 1
                    else:
                        logger.error(f"❌ Failed: {result.get('error', 'Unknown')}")
                        failed += 1
                
                import time
                time.sleep(3)
                balance_after = loop.run_until_complete(client.get_balance())
                
                recovered = balance_after - balance_before
                logger.info(f"🏁 Redemption complete! ✅ {success} | ❌ {failed} | 💵 +${recovered:.2f}")
                
                # Update balance on UI
                self._update_queue.put(("balance_update", balance_after))
                
            except Exception as e:
                logger.error(f"❌ Redeem error: {e}")
            finally:
                loop.close()
                # Re-enable button
                self.after(100, lambda: self.redeem_btn.configure(
                    state="normal", text="🎁 Redeem All"
                ))
        
        threading.Thread(target=run_redeem, daemon=True).start()
    
    def _on_copy_event(self, data):
        """Handle copy trade event or stats update from engine."""
        if isinstance(data, tuple):
            data_type, payload = data
            self._update_queue.put((data_type, payload))
        else:
            self._update_queue.put(("copy_event", data))
    
    # ─── UI Update Processing ───────────────────────────────────────────────
    def _process_updates(self):
        """Process queued UI updates."""
        try:
            while not self._update_queue.empty():
                update = self._update_queue.get_nowait()
                
                if update[0] == "status":
                    _, status, online = update
                    self.status_indicator.set_status(status, online)
                    
                elif update[0] == "connection":
                    _, status, online = update
                    self.connection_indicator.set_status(status, online)
                    
                elif update[0] == "copy_event":
                    result: CopyTradeResult = update[1]
                    self._add_copy_to_log(result)
                    self._update_copy_stats()
                    
                elif update[0] == "target_stats":
                    stats: WalletStats = update[1]
                    self._update_target_stats(stats)
                    
                elif update[0] == "user_stats":
                    stats: WalletStats = update[1]
                    self._update_user_stats(stats)
                    
                elif update[0] == "balance_update":
                    balance = update[1]
                    self.balance_label.configure(text=f"Balance: ${balance:,.2f}")
                    
                elif update[0] == "log":
                    _, msg, level = update
                    self.terminal.log(msg, level)
                    
                elif update[0] == "force_refresh":
                    # Period changed, engine will auto-refresh
                    pass
                    
        except Exception as e:
            # Don't log this to terminal to avoid potential infinite loops
            print(f"UI update error: {e}")
        
        self.after(50, self._process_updates) # Faster polling for terminal feel
    
    def _add_copy_to_log(self, result: CopyTradeResult):
        """Add a copy event to the activity log."""
        time_str = result.timestamp.strftime("%H:%M:%S")
        market = result.original_event.market_id[:15] + "..."
        side = result.original_event.side
        size = f"{result.copied_size:.4f}"
        price = f"${result.copied_price:.3f}"
        status = "Filled" if result.success else "Failed"
        
        self.trade_table.add_trade(time_str, market, side, size, price, status)
    
    def _update_copy_stats(self):
        """Update copy statistics display."""
        if not self.engine:
            return
        
        stats = self.engine.stats
        
        self.user_copies_stat.update_value(str(stats.total_copies))
        
        success_rate = (stats.successful_copies / stats.total_copies * 100) if stats.total_copies > 0 else 0
        self.user_success_stat.update_value(
            f"{success_rate:.1f}%",
            COLORS["success"] if success_rate > 50 else COLORS["danger"]
        )
        
        self.user_volume_stat.update_value(f"${stats.total_volume:,.2f}")
    
    def _update_target_stats(self, stats: WalletStats):
        """Update target wallet statistics display."""
        # Update period label
        period_labels = {
            "1D": "Last 24 Hours",
            "1M": "Last 30 Days",
            "1Y": "Last 365 Days",
            "ALL": "All Time"
        }
        self.target_period_label.configure(
            text=f"📅 Showing: {period_labels.get(stats.period, stats.period)}"
        )
        
        # P&L
        self.target_pnl.update(stats.total_pnl, stats.pnl_percentage)
        
        # Stats
        self.target_trades_stat.update_value(str(stats.total_trades))
        self.target_volume_stat.update_value(f"${stats.total_volume:,.2f}")
        self.target_winrate_stat.update_value(
            f"{stats.win_rate:.1f}%",
            get_pnl_color(stats.win_rate - 50)
        )
        
        # Positions
        self._update_positions_display("target", self.target_positions_container, stats.positions)
    
    def _update_user_stats(self, stats: WalletStats):
        """Update user wallet statistics display."""
        self.user_pnl.update(stats.total_pnl, stats.pnl_percentage)
        self._update_positions_display("user", self.user_positions_container, stats.positions)
        
        # Calculate redeemable amount (positions with current_price >= 0.95 are resolved winners)
        redeemable_positions = [
            p for p in stats.positions 
            if p.current_price >= 0.95 and p.size > 0
        ]
        redeemable_value = sum(p.size * p.current_price for p in redeemable_positions)
        
        # Store for redeem button
        self._redeemable_positions = redeemable_positions
        
        # Update redeemable stat card
        self.user_redeem_stat.update_value(
            f"${redeemable_value:,.2f}",
            COLORS["chart_green"] if redeemable_value > 0 else COLORS["text_muted"]
        )
        
        if redeemable_value > 0:
            self.redeem_btn.configure(state="normal")
        else:
            self.redeem_btn.configure(state="disabled")
    
    def _update_positions_display(self, panel_id: str, container: ctk.CTkScrollableFrame, positions: list):
        """Update positions display without flickering."""
        current_row_map = self._position_rows[panel_id]
        new_row_map = {}
        
        # Create/Update rows
        for pos in positions:
            pos_key = f"{pos.market_id}_{pos.outcome}"
            
            if pos_key in current_row_map:
                # Update existing row
                row = current_row_map[pos_key]
                row.update_data(pos.current_price, pos.unrealized_pnl)
                new_row_map[pos_key] = row
            else:
                # Remove "No positions" label if it exists
                for widget in container.winfo_children():
                    if isinstance(widget, ctk.CTkLabel) and widget.cget("text") == "No active positions":
                        widget.destroy()

                # Create new row
                row = PositionRow(
                    container,
                    market=pos.market_question,
                    outcome=pos.outcome,
                    size=pos.size,
                    avg_price=pos.avg_price,
                    current_price=pos.current_price,
                    pnl=pos.unrealized_pnl
                )
                row.pack(fill="x", pady=(0, SPACING["sm"]))
                new_row_map[pos_key] = row
        
        # Remove old rows that are no longer active
        for key, row in current_row_map.items():
            if key not in new_row_map:
                row.destroy()
        
        self._position_rows[panel_id] = new_row_map
        
        # Show "No positions" if empty
        if not new_row_map and not container.winfo_children():
            ctk.CTkLabel(
                container,
                text="No active positions",
                font=FONTS["body"],
                text_color=COLORS["text_muted"]
            ).pack(pady=SPACING["md"])
    
    # ─── Settings Dialog ────────────────────────────────────────────────────
    def _save_to_env(self, keys_map: dict):
        """Write settings to .env file."""
        try:
            from pathlib import Path
            env_path = Path(__file__).parent.parent.parent / ".env"
            lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
            
            s = self.settings
            for setting_key, env_key in keys_map.items():
                val = getattr(s, setting_key, "")
                new_line = f"{env_key}={val}"
                found = False
                for i, line in enumerate(lines):
                    if line.strip().startswith(f"{env_key}="):
                        lines[i] = new_line
                        found = True
                        break
                if not found:
                    lines.append(new_line)
            
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            logger.info("💾 Settings saved to .env!")
        except Exception as e:
            logger.warning(f"Could not write .env: {e}")
    
    def _apply_entries(self, entries: dict, type_map: dict):
        """Apply UI entries to settings object."""
        s = self.settings
        for key, entry in entries.items():
            try:
                val = entry.get() if isinstance(entry, (ctk.BooleanVar, ctk.StringVar)) else entry.get()
                cast = type_map.get(key, str)
                if cast == bool:
                    typed_val = val if isinstance(val, bool) else str(val).lower() in ("true", "1", "yes")
                else:
                    typed_val = cast(val)
                setattr(s, key, typed_val)
            except Exception as e:
                logger.warning(f"Could not save {key}: {e}")
    
    def _show_settings_dialog(self):
        """Show Trading Settings dialog with Risk Management button."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("⚙️ Trading Settings")
        dialog.geometry("480x520")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        
        content = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["lg"])
        
        s = self.settings
        entries = {}
        
        # ─── Helpers (local) ───
        def add_input(label, key, default, placeholder="", width=None):
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(row, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=placeholder or str(default), font=FONTS["small"],
                fg_color=COLORS["bg_secondary"], border_color=COLORS["border"], height=32, width=width or 120)
            entry.insert(0, str(getattr(s, key, default)))
            entry.pack(side="right")
            entries[key] = entry
        
        def add_dropdown(label, key, options, default):
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(row, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(side="left")
            var = ctk.StringVar(value=str(getattr(s, key, default)))
            ctk.CTkOptionMenu(row, variable=var, values=options, fg_color=COLORS["bg_secondary"],
                button_color=COLORS["accent_primary"], height=32, width=140).pack(side="right")
            entries[key] = var
        
        # ═══════════════════════════════════════════
        ctk.CTkLabel(content, text="⚙️ Trading Settings", font=FONTS["heading"],
            text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, SPACING["md"]))
        
        add_dropdown("Wallet Type", "wallet_type", ["metamask", "polymarket"], "metamask")
        add_input("Target Wallet", "target_wallet_address", s.target_wallet_address, "0x...", width=240)
        add_dropdown("Copy Mode", "copy_mode", ["proportional", "fixed", "mirror"], "proportional")
        add_input("Scale Factor", "scale_factor", s.scale_factor, "1.0")
        add_input("Fixed Amount ($)", "fixed_trade_amount", s.fixed_trade_amount, "10")
        add_input("Max Trade ($)", "max_trade_amount", s.max_trade_amount, "100")
        
        # ─── Info Box ───
        info_frame = ctk.CTkFrame(content, fg_color=COLORS["bg_tertiary"], corner_radius=RADIUS["md"])
        info_frame.pack(fill="x", pady=(SPACING["md"], SPACING["sm"]))
        ctk.CTkLabel(info_frame,
            text="ℹ️ MetaMask mode: signature_type=0 (EOA)\n"
                 "API keys auto-derived from private key.\n"
                 "Set PRIVATE_KEY in .env file.",
            font=FONTS["small"], text_color=COLORS["text_muted"], justify="left"
        ).pack(padx=SPACING["md"], pady=SPACING["sm"])
        
        # ─── Risk Management Button ───
        ActionButton(
            content, text="🛡️ Risk Management", variant="secondary", icon="",
            command=lambda: self._show_risk_dialog(dialog)
        ).pack(fill="x", pady=(SPACING["sm"], 0))
        
        # ─── Save Button ───
        trade_env_keys = {
            "target_wallet_address": "TARGET_WALLET_ADDRESS",
            "copy_mode": "COPY_MODE", "scale_factor": "SCALE_FACTOR",
            "fixed_trade_amount": "FIXED_TRADE_AMOUNT", "max_trade_amount": "MAX_TRADE_AMOUNT",
        }
        trade_types = {
            "wallet_type": str, "target_wallet_address": str, "copy_mode": str,
            "scale_factor": float, "fixed_trade_amount": float, "max_trade_amount": float,
        }
        
        def save_trade():
            self._apply_entries(entries, trade_types)
            self._save_to_env(trade_env_keys)
            dialog.destroy()
            logger.info("✅ Trading settings saved!")
        
        ActionButton(content, text="💾 Save Settings", variant="primary", icon="",
            command=save_trade).pack(fill="x", pady=(SPACING["sm"], 0))
    
    def _show_risk_dialog(self, parent_dialog=None):
        """Show Risk Management settings in a separate dialog."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("🛡️ Risk Management")
        dialog.geometry("460x620")
        dialog.configure(fg_color=COLORS["bg_dark"])
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        
        # Release parent grab so this one takes focus
        if parent_dialog:
            try:
                parent_dialog.grab_release()
            except Exception:
                pass
        
        content = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=SPACING["lg"], pady=SPACING["lg"])
        
        s = self.settings
        entries = {}
        
        # ─── Helpers ───
        def section_header(text, icon=""):
            frame = ctk.CTkFrame(content, fg_color=COLORS["bg_tertiary"], corner_radius=RADIUS["sm"])
            frame.pack(fill="x", pady=(SPACING["md"], SPACING["xs"]))
            ctk.CTkLabel(frame, text=f"{icon} {text}", font=FONTS["body_bold"],
                text_color=COLORS["accent_primary"]).pack(anchor="w", padx=SPACING["md"], pady=SPACING["sm"])
        
        def add_input(label, key, default, placeholder=""):
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(row, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=placeholder or str(default), font=FONTS["small"],
                fg_color=COLORS["bg_secondary"], border_color=COLORS["border"], height=32, width=120)
            entry.insert(0, str(getattr(s, key, default)))
            entry.pack(side="right")
            entries[key] = entry
        
        def add_toggle(label, key, default=False):
            row = ctk.CTkFrame(content, fg_color="transparent")
            row.pack(fill="x", pady=(0, SPACING["xs"]))
            ctk.CTkLabel(row, text=label, font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(side="left")
            var = ctk.BooleanVar(value=getattr(s, key, default))
            ctk.CTkSwitch(row, text="", variable=var, onvalue=True, offvalue=False,
                fg_color=COLORS["bg_tertiary"], progress_color=COLORS["success"], width=40).pack(side="right")
            entries[key] = var
        
        # ═══════════════════════════════════════════
        ctk.CTkLabel(content, text="🛡️ Risk Management", font=FONTS["heading"],
            text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, SPACING["sm"]))
        
        # ─── HIGH IMPACT ───
        section_header("HIGH IMPACT", "🔴")
        add_input("Daily Loss Limit ($)", "daily_loss_limit", s.daily_loss_limit, "50")
        add_input("Max Daily Trades", "max_daily_trades", s.max_daily_trades, "0")
        add_input("Max Open Positions", "max_open_positions", s.max_open_positions, "10")
        add_input("Min Price (0-1)", "min_price_filter", s.min_price_filter, "0.10")
        add_input("Max Price (0-1)", "max_price_filter", s.max_price_filter, "0.95")
        add_input("Balance Protection ($)", "balance_protection", s.balance_protection, "5")
        
        # ─── MEDIUM IMPACT ───
        section_header("MEDIUM IMPACT", "🟡")
        add_toggle("Skip SELL Copies", "skip_sell_copies", s.skip_sell_copies)
        add_input("Cooldown (seconds)", "cooldown_seconds", s.cooldown_seconds, "0")
        add_input("Per-Market Limit ($)", "per_market_limit", s.per_market_limit, "0")
        
        # ─── ADVANCED ───
        section_header("ADVANCED", "🔬")
        add_input("Min Win Rate (%)", "min_target_winrate", s.min_target_winrate, "0")
        add_input("Skip Expiring (hrs)", "skip_expiring_hours", s.skip_expiring_hours, "0")
        
        # ─── Tips ───
        tips = ctk.CTkFrame(content, fg_color=COLORS["bg_tertiary"], corner_radius=RADIUS["md"])
        tips.pack(fill="x", pady=(SPACING["md"], SPACING["sm"]))
        ctk.CTkLabel(tips,
            text="💡 Recommended defaults:\n"
                 "  Daily Loss: $50 | Min: 0.10 | Max: 0.95\n"
                 "  Balance Protect: $5 | Cooldown: 5s\n"
                 "  Set any value to 0 to disable it",
            font=FONTS["small"], text_color=COLORS["text_muted"], justify="left"
        ).pack(padx=SPACING["md"], pady=SPACING["sm"])
        
        # ─── Save ───
        risk_env_keys = {
            "daily_loss_limit": "DAILY_LOSS_LIMIT", "max_daily_trades": "MAX_DAILY_TRADES",
            "max_open_positions": "MAX_OPEN_POSITIONS",
            "min_price_filter": "MIN_PRICE_FILTER", "max_price_filter": "MAX_PRICE_FILTER",
            "balance_protection": "BALANCE_PROTECTION", "skip_sell_copies": "SKIP_SELL_COPIES",
            "cooldown_seconds": "COOLDOWN_SECONDS", "per_market_limit": "PER_MARKET_LIMIT",
            "min_target_winrate": "MIN_TARGET_WINRATE", "skip_expiring_hours": "SKIP_EXPIRING_HOURS",
        }
        risk_types = {
            "daily_loss_limit": float, "max_daily_trades": int, "max_open_positions": int,
            "min_price_filter": float, "max_price_filter": float,
            "balance_protection": float, "skip_sell_copies": bool,
            "cooldown_seconds": int, "per_market_limit": float,
            "min_target_winrate": float, "skip_expiring_hours": int,
        }
        
        def save_risk():
            self._apply_entries(entries, risk_types)
            self._save_to_env(risk_env_keys)
            dialog.destroy()
            # Re-grab parent if it exists
            if parent_dialog and parent_dialog.winfo_exists():
                try:
                    parent_dialog.grab_set()
                except Exception:
                    pass
            logger.info("✅ Risk management settings saved!")
        
        ActionButton(content, text="💾 Save Risk Settings", variant="primary", icon="",
            command=save_risk).pack(fill="x", pady=(SPACING["sm"], 0))


    def _on_close(self):
        """Handle window close."""
        import sys
        logger.info("Exiting application...")
        if self.engine:
            self.engine._is_running = False
        
        self.destroy()
        sys.exit(0)


def run_dashboard():
    """Run the dashboard application."""
    dashboard = Dashboard()
    dashboard.mainloop()


if __name__ == "__main__":
    run_dashboard()
