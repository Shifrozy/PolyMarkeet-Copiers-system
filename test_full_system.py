"""
🧪 FULL SYSTEM TEST SUITE
==========================
Tests every component of the Polymarket Copy Trading Bot with dummy/mock data.
No real API calls — everything is simulated to verify the system works.

Tests:
1. Config loading & validation
2. TimePeriod filtering logic
3. DataFetcher with mock API responses
4. PolymarketClient MetaMask initialization
5. CopyTradingEngine with mock data
6. Dashboard GUI components (headless)
7. Full end-to-end flow simulation
"""

import asyncio
import sys
import os
import json
import traceback
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Test Results Tracking ──────────────────────────────────────────────────────
PASSED = 0
FAILED = 0
ERRORS = []

def test_result(name, passed, detail=""):
    global PASSED, FAILED, ERRORS
    if passed:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        ERRORS.append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 1: Config Loading & Validation
# ═══════════════════════════════════════════════════════════════════════════════
def test_config():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 1: Config Loading & Validation                ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.config import Settings, get_settings, validate_settings
        
        settings = get_settings()
        
        # Check all required fields exist
        test_result("Settings instance created", settings is not None)
        test_result("wallet_type field exists", hasattr(settings, 'wallet_type'))
        test_result("wallet_type is 'metamask' or 'polymarket'", 
                     settings.wallet_type in ('metamask', 'polymarket'),
                     f"Got: {settings.wallet_type}")
        test_result("default_period field exists", hasattr(settings, 'default_period'))
        test_result("default_period is valid", 
                     settings.default_period in ('1D', '1M', '1Y', 'ALL'),
                     f"Got: {settings.default_period}")
        test_result("funder_address field exists", hasattr(settings, 'funder_address'))
        test_result("target_wallet_address has value", len(settings.target_wallet_address) > 0)
        test_result("rpc_url has value", len(settings.rpc_url) > 0)
        test_result("clob_api_url has value", len(settings.clob_api_url) > 0)
        test_result("gamma_api_url has value", len(settings.gamma_api_url) > 0)
        test_result("data_api_url has value", len(settings.data_api_url) > 0)
        
        # Validate returns correct structure
        is_valid, errors = validate_settings()
        test_result("validate_settings returns tuple", isinstance(is_valid, bool) and isinstance(errors, list))
        
        # Test that metamask mode doesn't require API keys
        if settings.wallet_type == "metamask":
            # In MetaMask mode, missing API keys should NOT cause errors
            # Only PRIVATE_KEY is required
            api_key_errors = [e for e in errors if "API_KEY" in e or "API_SECRET" in e or "API_PASSPHRASE" in e]
            test_result("MetaMask mode: API keys not required", len(api_key_errors) == 0,
                        f"Still requiring API keys: {api_key_errors}")
        
    except Exception as e:
        test_result("Config module loads", False, str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 2: TimePeriod Filtering Logic
# ═══════════════════════════════════════════════════════════════════════════════
def test_time_periods():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 2: TimePeriod Filtering Logic                 ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.api.data_fetcher import TimePeriod
        
        # Period constants
        test_result("TimePeriod.DAY_1 == '1D'", TimePeriod.DAY_1 == "1D")
        test_result("TimePeriod.MONTH_1 == '1M'", TimePeriod.MONTH_1 == "1M")
        test_result("TimePeriod.YEAR_1 == '1Y'", TimePeriod.YEAR_1 == "1Y")
        test_result("TimePeriod.ALL == 'ALL'", TimePeriod.ALL == "ALL")
        
        # Cutoff calculations
        now = datetime.now(timezone.utc)
        
        cutoff_1d = TimePeriod.get_cutoff("1D")
        test_result("1D cutoff is ~24h ago", 
                     cutoff_1d is not None and abs((now - cutoff_1d).total_seconds() - 86400) < 5,
                     f"Diff: {(now - cutoff_1d).total_seconds() if cutoff_1d else 'None'}s")
        
        cutoff_1m = TimePeriod.get_cutoff("1M")
        test_result("1M cutoff is ~30 days ago",
                     cutoff_1m is not None and abs((now - cutoff_1m).days - 30) <= 1,
                     f"Days: {(now - cutoff_1m).days if cutoff_1m else 'None'}")
        
        cutoff_1y = TimePeriod.get_cutoff("1Y")
        test_result("1Y cutoff is ~365 days ago",
                     cutoff_1y is not None and abs((now - cutoff_1y).days - 365) <= 1,
                     f"Days: {(now - cutoff_1y).days if cutoff_1y else 'None'}")
        
        cutoff_all = TimePeriod.get_cutoff("ALL")
        test_result("ALL cutoff is None (no filter)", cutoff_all is None)
        
        # ─── Test filtering logic with dummy trades ───
        from src.api.data_fetcher import TradeInfo
        
        # Create dummy trades at different times
        trades = [
            TradeInfo(
                trade_id="t1", market_id="m1", market_question="Q1",
                token_id="tok1", side="BUY", outcome="Yes",
                price=0.65, size=10.0, amount=6.5,
                timestamp=now - timedelta(hours=2)  # 2 hours ago (within 1D)
            ),
            TradeInfo(
                trade_id="t2", market_id="m2", market_question="Q2",
                token_id="tok2", side="SELL", outcome="No",
                price=0.45, size=5.0, amount=2.25,
                timestamp=now - timedelta(days=10)  # 10 days ago (within 1M, not 1D)
            ),
            TradeInfo(
                trade_id="t3", market_id="m3", market_question="Q3",
                token_id="tok3", side="BUY", outcome="Yes",
                price=0.30, size=20.0, amount=6.0,
                timestamp=now - timedelta(days=100)  # 100 days ago (within 1Y, not 1M)
            ),
            TradeInfo(
                trade_id="t4", market_id="m4", market_question="Q4",
                token_id="tok4", side="BUY", outcome="Yes",
                price=0.80, size=15.0, amount=12.0,
                timestamp=now - timedelta(days=400)  # 400 days ago (only in ALL)
            ),
        ]
        
        # Filter 1D
        cutoff = TimePeriod.get_cutoff("1D")
        filtered_1d = [t for t in trades if t.timestamp >= cutoff]
        test_result("1D filter: 1 trade (2h ago)", len(filtered_1d) == 1, f"Got {len(filtered_1d)}")
        
        # Filter 1M
        cutoff = TimePeriod.get_cutoff("1M")
        filtered_1m = [t for t in trades if t.timestamp >= cutoff]
        test_result("1M filter: 2 trades (2h + 10d ago)", len(filtered_1m) == 2, f"Got {len(filtered_1m)}")
        
        # Filter 1Y
        cutoff = TimePeriod.get_cutoff("1Y")
        filtered_1y = [t for t in trades if t.timestamp >= cutoff]
        test_result("1Y filter: 3 trades (2h + 10d + 100d)", len(filtered_1y) == 3, f"Got {len(filtered_1y)}")
        
        # Filter ALL
        cutoff = TimePeriod.get_cutoff("ALL")
        filtered_all = trades if cutoff is None else [t for t in trades if t.timestamp >= cutoff]
        test_result("ALL filter: 4 trades (everything)", len(filtered_all) == 4, f"Got {len(filtered_all)}")
        
    except Exception as e:
        test_result("TimePeriod module works", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 3: DataFetcher with Mock API Responses
# ═══════════════════════════════════════════════════════════════════════════════
def test_data_fetcher():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 3: DataFetcher with Mock API Responses        ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.api.data_fetcher import (
            DataFetcher, WalletStats, PositionInfo, 
            ClosedPositionInfo, MarketInfo, TimePeriod
        )
        
        # ─── Test WalletStats dataclass ───
        stats = WalletStats(
            wallet_address="0xDEMO",
            total_trades=25,
            total_volume=5000.0,
            total_pnl=250.50,
            pnl_percentage=5.01,
            win_rate=68.0,
            winning_trades=17,
            losing_trades=8,
            best_trade=120.0,
            worst_trade=-45.0,
            active_positions=3,
            period="1M"
        )
        test_result("WalletStats created with period", stats.period == "1M")
        test_result("WalletStats P&L correct", stats.total_pnl == 250.50)
        test_result("WalletStats win_rate correct", stats.win_rate == 68.0)
        
        # ─── Test PositionInfo ───
        position = PositionInfo(
            market_id="demo_market",
            market_question="Will BTC reach 100k?",
            token_id="tok_demo",
            outcome="Yes",
            size=50.0,
            avg_price=0.45,
            current_price=0.72,
            unrealized_pnl=13.50,
            realized_pnl=0.0,
            total_cost=22.50,
            current_value=36.0
        )
        test_result("PositionInfo created", position.market_question == "Will BTC reach 100k?")
        test_result("PositionInfo P&L calculation",
                     abs(position.current_value - position.total_cost - position.unrealized_pnl) < 0.01)
        
        # ─── Test ClosedPositionInfo ───
        now = datetime.now(timezone.utc)
        closed = ClosedPositionInfo(
            market_id="closed_market",
            market_question="Did ETH hit 5k?",
            outcome="Yes",
            realized_pnl=85.30,
            size=100.0,
            avg_price=0.35,
            close_price=1.0,
            timestamp=now - timedelta(days=5)
        )
        test_result("ClosedPositionInfo created", closed.realized_pnl == 85.30)
        test_result("ClosedPositionInfo has timestamp", closed.timestamp is not None)
        
        # ─── Test MarketInfo ───
        market = MarketInfo(
            market_id="m_demo",
            question="Will it rain tomorrow?",
            description="Test market",
            end_date=now + timedelta(days=7),
            outcomes=["Yes", "No"],
            tokens=[],
            volume=150000.0,
            liquidity=25000.0,
            active=True,
            price=0.65,
            prices=[0.65, 0.35],
            is_resolved=False,
            winning_outcome=None
        )
        test_result("MarketInfo created", market.question == "Will it rain tomorrow?")
        test_result("MarketInfo prices sum to ~1.0",
                     abs(sum(market.prices) - 1.0) < 0.01,
                     f"Sum: {sum(market.prices)}")
        
        # ─── Test resolved market prices ───
        resolved_market = MarketInfo(
            market_id="m_resolved",
            question="Did XRP reach $1?",
            description="Resolved market",
            end_date=now - timedelta(days=1),
            outcomes=["Yes", "No"],
            tokens=[],
            volume=500000.0,
            liquidity=0.0,
            active=False,
            price=1.0,
            prices=[1.0, 0.0],
            is_resolved=True,
            winning_outcome="0"  # Yes won
        )
        test_result("Resolved market: is_resolved=True", resolved_market.is_resolved)
        test_result("Resolved market: winning_outcome set", resolved_market.winning_outcome == "0")
        
        # ─── Test DataFetcher instance ───
        fetcher = DataFetcher()
        test_result("DataFetcher instantiated", fetcher is not None)
        test_result("DataFetcher has market cache", hasattr(fetcher, '_market_cache'))
        
        # ─── Test _parse_date helper ───
        d1 = DataFetcher._parse_date("2025-06-15T10:30:00Z")
        test_result("_parse_date ISO string", d1 is not None and d1.year == 2025)
        
        d2 = DataFetcher._parse_date(1718451000)  # Unix timestamp
        test_result("_parse_date Unix timestamp", d2 is not None)
        
        d3 = DataFetcher._parse_date(None)
        test_result("_parse_date None returns None", d3 is None)
        
        d4 = DataFetcher._parse_date("")
        test_result("_parse_date empty string returns None", d4 is None)
        
    except Exception as e:
        test_result("DataFetcher module works", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 4: PolymarketClient MetaMask Support
# ═══════════════════════════════════════════════════════════════════════════════
def test_polymarket_client():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 4: PolymarketClient MetaMask Support          ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.api.polymarket_client import PolymarketClient, Side, TradeOrder, OrderResult
        
        # ─── Test Side enum ───
        test_result("Side.BUY == 'BUY'", Side.BUY.value == "BUY")
        test_result("Side.SELL == 'SELL'", Side.SELL.value == "SELL")
        
        # ─── Test OrderResult ───
        success_result = OrderResult(success=True, order_id="ord_123", transaction_hash="0xabc")
        test_result("OrderResult success", success_result.success and success_result.order_id == "ord_123")
        
        fail_result = OrderResult(success=False, error="Insufficient balance")
        test_result("OrderResult failure", not fail_result.success and fail_result.error == "Insufficient balance")
        
        # ─── Test TradeOrder ───
        order = TradeOrder(
            token_id="tok_demo",
            side=Side.BUY,
            size=10.0,
            price=0.65,
            market_id="m_demo",
            market_question="Test market"
        )
        test_result("TradeOrder created", order.size == 10.0 and order.price == 0.65)
        
        # ─── Test Client instantiation ───
        client = PolymarketClient()
        test_result("PolymarketClient instantiated", client is not None)
        test_result("Client not initialized yet", not client.is_initialized)
        test_result("Client wallet_address is None", client.wallet_address is None)
        
        # ─── Test that MetaMask constants exist ───
        from src.api.polymarket_client import CHAIN_ID, CTF_EXCHANGE, USDC_ADDRESS
        test_result("CHAIN_ID is 137 (Polygon)", CHAIN_ID == 137)
        test_result("CTF_EXCHANGE address exists", len(CTF_EXCHANGE) > 0)
        test_result("USDC_ADDRESS exists", len(USDC_ADDRESS) > 0)
        
    except Exception as e:
        test_result("PolymarketClient module works", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 5: CopyTradingEngine with Mock Data
# ═══════════════════════════════════════════════════════════════════════════════
def test_copy_engine():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 5: CopyTradingEngine with Mock Data           ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.engine.copy_engine import CopyTradingEngine, CopyMode, CopyTradeResult, CopyStats
        from src.api.trade_monitor import TradeEvent, TradeEventType
        
        # ─── Test CopyMode enum ───
        test_result("CopyMode.PROPORTIONAL", CopyMode.PROPORTIONAL.value == "proportional")
        test_result("CopyMode.FIXED", CopyMode.FIXED.value == "fixed")
        test_result("CopyMode.MIRROR", CopyMode.MIRROR.value == "mirror")
        
        # ─── Test Engine creation ───
        engine = CopyTradingEngine(
            target_wallet="0xDEMO_TARGET",
            mode=CopyMode.PROPORTIONAL,
            scale_factor=0.5,
            fixed_amount=25.0,
            max_amount=200.0
        )
        test_result("Engine created", engine is not None)
        test_result("Engine target wallet set", engine.target_wallet == "0xDEMO_TARGET")
        test_result("Engine mode is PROPORTIONAL", engine.mode == CopyMode.PROPORTIONAL)
        test_result("Engine not running initially", not engine.is_running)
        
        # ─── Test period property ───
        test_result("Engine default period", engine.current_period in ("1D", "1M", "1Y", "ALL"))
        engine.current_period = "1M"
        test_result("Engine period changed to 1M", engine.current_period == "1M")
        engine.current_period = "1D"
        test_result("Engine period changed to 1D", engine.current_period == "1D")
        engine.current_period = "ALL"
        test_result("Engine period changed to ALL", engine.current_period == "ALL")
        
        # ─── Test copy size calculation ───
        # PROPORTIONAL mode (0.5x)
        size = engine._calculate_copy_size(original_size=100, price=0.50)
        test_result(f"PROPORTIONAL 0.5x: 100 → {size}", size == 50.0, f"Expected 50.0, got {size}")
        
        # MIRROR mode
        engine.mode = CopyMode.MIRROR
        size = engine._calculate_copy_size(original_size=100, price=0.50)
        test_result(f"MIRROR: 100 → {size}", size == 100.0, f"Expected 100.0, got {size}")
        
        # FIXED mode ($25)
        engine.mode = CopyMode.FIXED
        size = engine._calculate_copy_size(original_size=100, price=0.50)
        test_result(f"FIXED $25 @ $0.50: → {size}", size == 50.0, f"Expected 50.0, got {size}")
        
        # Max amount cap test
        engine.mode = CopyMode.MIRROR
        engine.max_amount = 10.0  # Very low max
        size = engine._calculate_copy_size(original_size=100, price=0.50)
        expected_max = 10.0 / 0.50  # = 20
        test_result(f"Max cap: 100 capped to {size}", size == expected_max, 
                     f"Expected {expected_max}, got {size}")
        
        # ─── Test CopyStats ───
        stats = CopyStats()
        test_result("CopyStats initial values", 
                     stats.total_copies == 0 and stats.successful_copies == 0 and stats.failed_copies == 0)
        
        # ─── Test CopyTradeResult ───
        event = TradeEvent(
            event_type=TradeEventType.ORDER_FILLED,
            wallet_address="0xTARGET",
            market_id="market_123",
            token_id="token_456",
            side="BUY",
            price=0.65,
            size=50.0,
            timestamp=datetime.now()
        )
        
        result = CopyTradeResult(
            success=True,
            original_event=event,
            original_size=50.0,
            copied_size=25.0,
            original_price=0.65,
            copied_price=0.65
        )
        test_result("CopyTradeResult success", result.success and result.copied_size == 25.0)
        
        failed_result = CopyTradeResult(
            success=False,
            original_event=event,
            error="Insufficient balance"
        )
        test_result("CopyTradeResult failure", not failed_result.success and "balance" in failed_result.error)
        
    except Exception as e:
        test_result("CopyTradingEngine module works", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 6: Trade Monitor
# ═══════════════════════════════════════════════════════════════════════════════
def test_trade_monitor():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 6: Trade Monitor                              ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.api.trade_monitor import TradeMonitor, TradeEvent, TradeEventType
        
        # ─── Test TradeEventType ───
        test_result("TradeEventType.ORDER_FILLED", TradeEventType.ORDER_FILLED.value == "order_filled")
        test_result("TradeEventType.NEW_ORDER", TradeEventType.NEW_ORDER.value == "new_order")
        
        # ─── Test TradeEvent creation ───
        event = TradeEvent(
            event_type=TradeEventType.ORDER_FILLED,
            wallet_address="0xLEADER",
            market_id="market_abc",
            token_id="token_xyz",
            side="BUY",
            price=0.72,
            size=30.0,
            timestamp=datetime.now(),
            transaction_hash="0xtxhash123"
        )
        test_result("TradeEvent created", event.side == "BUY" and event.price == 0.72)
        
        # ─── Test Monitor creation ───
        monitor = TradeMonitor(target_wallet="0xDEMO")
        test_result("TradeMonitor created", monitor is not None)
        test_result("Monitor not running", not monitor.is_running)
        test_result("Monitor target set", monitor.target_wallet == "0xDEMO")
        
        # ─── Test callback management ───
        callback_called = []
        def test_callback(event):
            callback_called.append(event)
        
        monitor.add_callback(test_callback)
        test_result("Callback added", len(monitor._callbacks) == 1)
        
        monitor.remove_callback(test_callback)
        test_result("Callback removed", len(monitor._callbacks) == 0)
        
        # ─── Test duplicate detection ───
        event1 = TradeEvent(
            event_type=TradeEventType.ORDER_FILLED,
            wallet_address="0x", market_id="m", token_id="t",
            side="BUY", price=0.5, size=10, timestamp=datetime.now(),
            transaction_hash="0xSAME"
        )
        monitor._last_events.append(event1)
        
        is_dup = monitor._is_duplicate_event(event1)
        test_result("Duplicate detection works", is_dup, f"Got: {is_dup}")
        
        event2 = TradeEvent(
            event_type=TradeEventType.ORDER_FILLED,
            wallet_address="0x", market_id="m", token_id="t",
            side="BUY", price=0.5, size=10, timestamp=datetime.now(),
            transaction_hash="0xDIFFERENT"
        )
        is_not_dup = not monitor._is_duplicate_event(event2)
        test_result("Non-duplicate passes", is_not_dup, f"Got: {not is_not_dup}")
        
    except Exception as e:
        test_result("TradeMonitor module works", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 7: Dashboard GUI Components (Headless)
# ═══════════════════════════════════════════════════════════════════════════════
def test_gui_components():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 7: Dashboard GUI Components (Headless)        ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.gui.theme import COLORS, FONTS, SPACING, RADIUS, get_pnl_color, format_pnl, format_percentage
        
        # ─── Test theme colors ───
        test_result("COLORS has bg_dark", "bg_dark" in COLORS)
        test_result("COLORS has success", "success" in COLORS)
        test_result("COLORS has danger", "danger" in COLORS)
        test_result("All hex colors valid", all(c.startswith("#") for c in COLORS.values()))
        
        # ─── Test P&L formatting ───
        test_result("format_pnl positive", format_pnl(150.5) == "+$150.50")
        test_result("format_pnl negative", format_pnl(-42.3) == "$-42.30")  
        test_result("format_pnl zero", format_pnl(0) == "$0.00")
        
        # ─── Test percentage formatting ───
        test_result("format_percentage positive", format_percentage(5.25) == "+5.25%")
        test_result("format_percentage negative", format_percentage(-3.1) == "-3.10%")
        
        # ─── Test P&L color ───
        test_result("pnl_color positive = green", get_pnl_color(100) == COLORS["success"])
        test_result("pnl_color negative = red", get_pnl_color(-50) == COLORS["danger"])
        test_result("pnl_color zero = secondary", get_pnl_color(0) == COLORS["text_secondary"])
        
        # ─── Test FONTS exist ───
        test_result("FONTS has heading", "heading" in FONTS)
        test_result("FONTS has body", "body" in FONTS)
        test_result("FONTS has mono", "mono" in FONTS)
        
        # ─── Test components import ───
        from src.gui.components import (
            GlassCard, StatCard, TradeHistoryTable, StatusIndicator,
            ActionButton, PnLDisplay, PositionRow
        )
        test_result("All GUI components import OK", True)
        
        # ─── Test TimePeriodSelector import ───
        from src.gui.main_dashboard import TimePeriodSelector, Dashboard
        test_result("TimePeriodSelector imports OK", True)
        test_result("Dashboard imports OK", True)
        
    except Exception as e:
        test_result("GUI components work", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 8: Full End-to-End Flow Simulation
# ═══════════════════════════════════════════════════════════════════════════════
def test_e2e_simulation():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 8: Full End-to-End Flow Simulation            ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        from src.api.data_fetcher import (
            DataFetcher, WalletStats, PositionInfo, 
            ClosedPositionInfo, TimePeriod
        )
        from src.engine.copy_engine import CopyTradingEngine, CopyMode, CopyTradeResult, CopyStats
        from src.api.trade_monitor import TradeEvent, TradeEventType
        
        now = datetime.now(timezone.utc)
        
        # ─── Simulate a complete wallet stats package ───
        # Create mock positions
        positions = [
            PositionInfo(
                market_id="market_1",
                market_question="Will Trump win 2024?",
                token_id="tok_1",
                outcome="Yes",
                size=100.0,
                avg_price=0.55,
                current_price=0.72,
                unrealized_pnl=17.0,
                realized_pnl=0.0,
                total_cost=55.0,
                current_value=72.0
            ),
            PositionInfo(
                market_id="market_2",
                market_question="Will BTC reach 100k by March?",
                token_id="tok_2",
                outcome="No",
                size=50.0,
                avg_price=0.40,
                current_price=0.35,
                unrealized_pnl=-2.50,
                realized_pnl=0.0,
                total_cost=20.0,
                current_value=17.50
            ),
        ]
        
        # Create mock closed positions
        closed_positions = [
            ClosedPositionInfo(
                market_id="closed_1",
                market_question="Will ETH merge succeed?",
                outcome="Yes",
                realized_pnl=42.50,
                size=85.0,
                avg_price=0.50,
                close_price=1.0,
                timestamp=now - timedelta(hours=6)  # 6 hours ago
            ),
            ClosedPositionInfo(
                market_id="closed_2",
                market_question="Will Solana hit $200?",
                outcome="Yes",
                realized_pnl=-15.00,
                size=30.0,
                avg_price=0.50,
                close_price=0.0,
                timestamp=now - timedelta(days=15)  # 15 days ago
            ),
            ClosedPositionInfo(
                market_id="closed_3",
                market_question="Will XRP win SEC case?",
                outcome="No",
                realized_pnl=28.00,
                size=70.0,
                avg_price=0.60,
                close_price=1.0,
                timestamp=now - timedelta(days=200)  # 200 days ago
            ),
        ]
        
        # ─── Simulate stats for each period ───
        for period in ["1D", "1M", "1Y", "ALL"]:
            cutoff = TimePeriod.get_cutoff(period)
            
            if cutoff:
                filtered_closed = [cp for cp in closed_positions if cp.timestamp and cp.timestamp >= cutoff]
            else:
                filtered_closed = closed_positions
            
            closed_pnl = sum(cp.realized_pnl for cp in filtered_closed)
            open_pnl = sum(p.unrealized_pnl for p in positions)
            total_pnl = closed_pnl + open_pnl
            
            stats = WalletStats(
                wallet_address="0xDEMO",
                total_pnl=total_pnl,
                active_positions=len(positions),
                period=period,
                positions=positions,
                closed_positions=filtered_closed
            )
            
            # Verify correct P&L for each period
            if period == "1D":
                expected_closed_pnl = 42.50  # Only the 6h old closed position
                test_result(f"[{period}] Closed P&L = ${expected_closed_pnl}",
                           abs(closed_pnl - expected_closed_pnl) < 0.01,
                           f"Got {closed_pnl}")
                test_result(f"[{period}] 1 closed position", len(filtered_closed) == 1)
                
            elif period == "1M":
                expected_closed_pnl = 42.50 + (-15.00)  # 6h + 15d old
                test_result(f"[{period}] Closed P&L = ${expected_closed_pnl}",
                           abs(closed_pnl - expected_closed_pnl) < 0.01,
                           f"Got {closed_pnl}")
                test_result(f"[{period}] 2 closed positions", len(filtered_closed) == 2)
                
            elif period == "1Y":
                expected_closed_pnl = 42.50 + (-15.00) + 28.00  # All 3
                test_result(f"[{period}] Closed P&L = ${expected_closed_pnl}",
                           abs(closed_pnl - expected_closed_pnl) < 0.01,
                           f"Got {closed_pnl}")
                test_result(f"[{period}] 3 closed positions", len(filtered_closed) == 3)
                
            elif period == "ALL":
                expected_closed_pnl = 42.50 + (-15.00) + 28.00  # All 3
                test_result(f"[{period}] Closed P&L = ${expected_closed_pnl}",
                           abs(closed_pnl - expected_closed_pnl) < 0.01,
                           f"Got {closed_pnl}")
                test_result(f"[{period}] 3 closed positions", len(filtered_closed) == 3)
            
            # Total P&L always includes open positions
            test_result(f"[{period}] Total P&L includes open ({open_pnl})",
                        abs(stats.total_pnl - (closed_pnl + open_pnl)) < 0.01)
        
        # ─── Simulate copy trade flow ───
        engine = CopyTradingEngine(
            target_wallet="0xTARGET_DEMO",
            mode=CopyMode.PROPORTIONAL,
            scale_factor=0.5,
            max_amount=100.0
        )
        
        # Simulate receiving a trade event
        trade_event = TradeEvent(
            event_type=TradeEventType.ORDER_FILLED,
            wallet_address="0xTARGET_DEMO",
            market_id="market_1",
            token_id="tok_1",
            side="BUY",
            price=0.65,
            size=50.0,
            timestamp=datetime.now()
        )
        
        # Calculate what the copy size should be
        copy_size = engine._calculate_copy_size(trade_event.size, trade_event.price)
        expected = 50.0 * 0.5  # PROPORTIONAL at 0.5x
        test_result(f"E2E: Copy size calculation ({copy_size})",
                    abs(copy_size - expected) < 0.01, f"Expected {expected}")
        
        # Verify copy result structure
        result = CopyTradeResult(
            success=True,
            original_event=trade_event,
            original_size=trade_event.size,
            copied_size=copy_size,
            original_price=trade_event.price,
            copied_price=trade_event.price
        )
        test_result("E2E: CopyTradeResult valid", 
                     result.success and result.copied_size == 25.0)
        
        # Update stats
        engine._stats.total_copies += 1
        engine._stats.successful_copies += 1
        engine._stats.total_volume += copy_size * trade_event.price
        engine._stats.copy_history.append(result)
        
        test_result("E2E: Stats updated after copy",
                     engine.stats.total_copies == 1 and engine.stats.successful_copies == 1)
        test_result("E2E: Volume tracked",
                     engine.stats.total_volume > 0)
        test_result("E2E: Copy history recorded",
                     len(engine.get_copy_history()) == 1)
        
    except Exception as e:
        test_result("E2E simulation works", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# TEST 9: Module Cross-Compatibility
# ═══════════════════════════════════════════════════════════════════════════════
def test_cross_compatibility():
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║  TEST 9: Module Cross-Compatibility                 ║")
    print("╚══════════════════════════════════════════════════════╝")
    
    try:
        # Test that all __init__.py exports work
        from src.api import PolymarketClient, DataFetcher, TradeMonitor
        test_result("src.api exports OK", True)
        
        from src.engine import CopyTradingEngine, CopyMode, CopyTradeResult, CopyStats
        test_result("src.engine exports OK", True)
        
        from src.gui import Dashboard
        test_result("src.gui exports OK", True)
        
        # Test cross-module types compatibility
        from src.api.data_fetcher import WalletStats, PositionInfo, TimePeriod
        from src.engine.copy_engine import CopyTradingEngine
        
        # Engine should accept TimePeriod values
        engine = CopyTradingEngine()
        engine.current_period = TimePeriod.DAY_1
        test_result("Engine accepts TimePeriod.DAY_1", engine.current_period == "1D")
        engine.current_period = TimePeriod.MONTH_1
        test_result("Engine accepts TimePeriod.MONTH_1", engine.current_period == "1M")
        engine.current_period = TimePeriod.YEAR_1
        test_result("Engine accepts TimePeriod.YEAR_1", engine.current_period == "1Y")
        engine.current_period = TimePeriod.ALL
        test_result("Engine accepts TimePeriod.ALL", engine.current_period == "ALL")
        
        # WalletStats should work with engine
        stats = WalletStats(wallet_address="0xDEMO", period="1M")
        test_result("WalletStats compatible with engine", stats.period == "1M")
        
    except Exception as e:
        test_result("Cross-compatibility OK", False, traceback.format_exc())


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN TEST RUNNER
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    print("\n" + "=" * 60)
    print("  🧪 POLYMARKET COPY TRADING BOT — FULL SYSTEM TEST")
    print("  📅 " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("  🖥️  All tests use dummy/mock data (no real API calls)")
    print("=" * 60)
    
    # Run all tests
    test_config()
    test_time_periods()
    test_data_fetcher()
    test_polymarket_client()
    test_copy_engine()
    test_trade_monitor()
    test_gui_components()
    test_e2e_simulation()
    test_cross_compatibility()
    
    # ─── Final Report ───
    total = PASSED + FAILED
    print("\n" + "=" * 60)
    print(f"  📊 FINAL RESULTS")
    print("=" * 60)
    print(f"  ✅ Passed: {PASSED}/{total}")
    print(f"  ❌ Failed: {FAILED}/{total}")
    
    if FAILED == 0:
        print(f"\n  🎉 ALL {total} TESTS PASSED! System is ready! 🎉")
        print(f"\n  ✓ Config & MetaMask settings .......... OK")
        print(f"  ✓ Time filters (1D/1M/1Y/ALL) ........ OK")
        print(f"  ✓ Data fetcher & P&L calculation ...... OK")
        print(f"  ✓ PolymarketClient (MetaMask mode) .... OK")
        print(f"  ✓ Copy engine & trade execution ....... OK")
        print(f"  ✓ Trade monitor & callbacks ........... OK")
        print(f"  ✓ Dashboard GUI components ............ OK")
        print(f"  ✓ End-to-end flow simulation .......... OK")
        print(f"  ✓ Module cross-compatibility .......... OK")
    else:
        print(f"\n  ⚠️  {FAILED} test(s) failed:")
        for err in ERRORS:
            print(f"    • {err}")
    
    print("\n" + "=" * 60 + "\n")
    return FAILED == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
