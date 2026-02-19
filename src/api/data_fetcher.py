"""
Polymarket Data Fetcher
=======================
Fetches market data, trade history, and wallet information from Polymarket APIs.
Supports time-period filtering (1D, 1M, 1Y, ALL) for dashboard stats.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

import requests
import aiohttp

from src.config import get_settings

logger = logging.getLogger(__name__)


# ─── Time Period Enum ───────────────────────────────────────────────────────────
class TimePeriod:
    """Time period constants for filtering stats."""
    DAY_1 = "1D"
    MONTH_1 = "1M"
    YEAR_1 = "1Y"
    ALL = "ALL"

    @staticmethod
    def get_cutoff(period: str) -> Optional[datetime]:
        """Get the UTC cutoff datetime for a given period."""
        now = datetime.now(timezone.utc)
        if period == TimePeriod.DAY_1:
            return now - timedelta(days=1)
        elif period == TimePeriod.MONTH_1:
            return now - timedelta(days=30)
        elif period == TimePeriod.YEAR_1:
            return now - timedelta(days=365)
        return None  # ALL = no cutoff


# ─── Data Classes ───────────────────────────────────────────────────────────────
@dataclass
class MarketInfo:
    """Information about a Polymarket market."""
    market_id: str
    question: str
    description: str
    end_date: Optional[datetime]
    outcomes: List[str]
    tokens: List[Any]
    volume: float
    liquidity: float
    active: bool
    price: float = 0.5
    prices: List[float] = field(default_factory=list)
    is_resolved: bool = False
    winning_outcome: Optional[str] = None


@dataclass
class TradeInfo:
    """Information about a single trade."""
    trade_id: str
    market_id: str
    market_question: str
    token_id: str
    side: str  # "BUY" or "SELL"
    outcome: str  # "Yes" or "No"
    price: float
    size: float
    amount: float  # price * size
    timestamp: datetime
    transaction_hash: Optional[str] = None


@dataclass
class PositionInfo:
    """Information about a position."""
    market_id: str
    market_question: str
    token_id: str
    outcome: str
    size: float
    avg_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    total_cost: float
    current_value: float


@dataclass
class ClosedPositionInfo:
    """Information about a closed/resolved position."""
    market_id: str
    market_question: str
    outcome: str
    realized_pnl: float
    size: float
    avg_price: float
    close_price: float
    timestamp: Optional[datetime] = None


@dataclass
class WalletStats:
    """Statistics for a wallet."""
    wallet_address: str
    total_trades: int = 0
    total_volume: float = 0.0
    total_pnl: float = 0.0
    pnl_percentage: float = 0.0
    win_rate: float = 0.0
    winning_trades: int = 0
    losing_trades: int = 0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    active_positions: int = 0
    period: str = "ALL"
    positions: List[PositionInfo] = field(default_factory=list)
    trade_history: List[TradeInfo] = field(default_factory=list)
    closed_positions: List[ClosedPositionInfo] = field(default_factory=list)


# ─── Data Fetcher ───────────────────────────────────────────────────────────────
class DataFetcher:
    """Fetches market data and wallet stats from Polymarket APIs."""
    
    def __init__(self):
        self.settings = get_settings()
        self._market_cache: Dict[str, MarketInfo] = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize the persistent aiohttp session."""
        if not self._session:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
            logger.info("✅ Data fetcher aiohttp session initialized")
            
    async def close(self):
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("🛑 Data fetcher session closed")

    @property
    def session(self) -> aiohttp.ClientSession:
        if not self._session:
            # Fallback for sync-initialized calls if any
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    # ─── Trade History ──────────────────────────────────────────────────────
    async def get_wallet_trades(
        self,
        wallet_address: str,
        limit: int = 200
    ) -> List[TradeInfo]:
        """Get trade history for a specific wallet address."""
        all_trades = []
        try:
            url = f"{self.settings.data_api_url}/trades"
            params_user = {"user": wallet_address.lower(), "limit": limit}
            params_maker = {"maker": wallet_address.lower(), "limit": limit}
            
            async def fetch(p):
                async with self.session.get(url, params=p) as res:
                    return await res.json() if res.status == 200 else []

            results = await asyncio.gather(fetch(params_user), fetch(params_maker))
            
            user_data, maker_data = results
            logger.info(f"📥 Fetched {len(user_data)} taker trades and {len(maker_data)} maker trades for {wallet_address[:8]}...")
            
            for data in [user_data, maker_data]:
                if not data or not isinstance(data, list):
                    continue
                
                # Fetch market info in parallel for unknown markets
                market_ids = list(set(trade.get("market", "") for trade in data if trade))
                unknown_ids = [mid for mid in market_ids if mid and mid not in self._market_cache]
                if unknown_ids:
                    await asyncio.gather(*[self.get_market_info(mid) for mid in unknown_ids])
                
                for trade_data in data:
                    if not trade_data:
                        continue
                    
                    # When querying by maker/user specifically, we trust the API results
                    pass
                        
                    m_id = trade_data.get("conditionId") or trade_data.get("market") or ""
                    m_info = self._market_cache.get(m_id)
                    
                    # Parse timestamp
                    ts = trade_data.get("timestamp")
                    trade_time = datetime.now(timezone.utc)
                    if ts:
                        try:
                            if isinstance(ts, (int, float)):
                                trade_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                            else:
                                ts_str = str(ts).replace('Z', '+00:00')
                                trade_time = datetime.fromisoformat(ts_str)
                                if trade_time.tzinfo is None:
                                    trade_time = trade_time.replace(tzinfo=timezone.utc)
                        except:
                            pass
                    
                    trade = TradeInfo(
                        trade_id=str(trade_data.get("id") or trade_data.get("transactionHash") or ""),
                        market_id=m_id,
                        market_question=m_info.question if m_info else "Unknown",
                        token_id=trade_data.get("asset") or trade_data.get("asset_id") or "",
                        side=trade_data.get("side", "").upper(),
                        outcome=trade_data.get("outcome", ""),
                        price=float(trade_data.get("price", 0)),
                        size=float(trade_data.get("size", 0)),
                        amount=float(trade_data.get("price", 0)) * float(trade_data.get("size", 0)),
                        timestamp=trade_time,
                        transaction_hash=trade_data.get("transactionHash")
                    )
                    if not any(t.trade_id == trade.trade_id for t in all_trades):
                        all_trades.append(trade)
            
            # Sort by timestamp desc and limit to the requested amount
            all_trades.sort(key=lambda x: x.timestamp, reverse=True)
            return all_trades[:limit]
        except Exception as e:
            logger.error(f"Error fetching trades: {e}")
            return all_trades

    # ─── Closed Positions ───────────────────────────────────────────────────
    async def get_wallet_closed_positions(
        self,
        wallet_address: str,
        limit: int = 200
    ) -> List[ClosedPositionInfo]:
        """Fetch closed positions with full details for realized P&L."""
        closed = []
        try:
            url = f"{self.settings.data_api_url}/closed-positions"
            params = {"user": wallet_address.lower(), "limit": limit}
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if not isinstance(data, list):
                        return closed
                    
                    # Pre-fetch market info in parallel for unknown markets
                    market_ids = list(set(pos.get("conditionId") or pos.get("market") or "" for pos in data if pos))
                    unknown_ids = [mid for mid in market_ids if mid and mid not in self._market_cache]
                    if unknown_ids:
                        await asyncio.gather(*[self.get_market_info(mid) for mid in unknown_ids])

                    for pos in data:
                        market_id = pos.get("conditionId") or pos.get("market") or ""
                        m_info = self._market_cache.get(market_id)
                        
                        # Parse close timestamp
                        ts = pos.get("closedAt") or pos.get("timestamp") or pos.get("updatedAt")
                        close_time = None
                        if ts:
                            try:
                                if isinstance(ts, (int, float)):
                                    close_time = datetime.fromtimestamp(ts, tz=timezone.utc)
                                else:
                                    ts_str = str(ts).replace('Z', '+00:00')
                                    close_time = datetime.fromisoformat(ts_str)
                                    if close_time.tzinfo is None:
                                        close_time = close_time.replace(tzinfo=timezone.utc)
                            except:
                                pass
                        
                        cp = ClosedPositionInfo(
                            market_id=market_id,
                            market_question=m_info.question if m_info else f"Market {market_id[:8]}",
                            outcome=str(pos.get("outcome", "")),
                            realized_pnl=float(pos.get("realizedPnl") or 0),
                            size=float(pos.get("size") or 0),
                            avg_price=float(pos.get("avgPrice") or pos.get("averagePrice") or 0),
                            close_price=float(pos.get("closePrice") or pos.get("currentPrice") or 0),
                            timestamp=close_time
                        )
                        closed.append(cp)
            return closed
        except Exception as e:
            logger.error(f"Error fetching closed positions: {e}")
            return closed
    
    # ─── Open Positions ─────────────────────────────────────────────────────
    async def get_wallet_positions(self, wallet_address: str) -> List[PositionInfo]:
        """Get current open positions for a wallet address."""
        try:
            url = f"{self.settings.data_api_url}/positions"
            params = {"user": wallet_address.lower()}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    positions = []
                    
                    # Pre-fetch market info in parallel for unknown markets
                    all_market_ids = list(set(pos.get("conditionId") or pos.get("market") or pos.get("marketId") or "" for pos in data if pos))
                    unknown_ids = [mid for mid in all_market_ids if mid and mid not in self._market_cache]
                    if unknown_ids:
                        await asyncio.gather(*[self.get_market_info(mid) for mid in unknown_ids])

                    for pos_data in data:
                        market_id = pos_data.get("conditionId") or pos_data.get("market") or pos_data.get("marketId") or ""
                        market_info = self._market_cache.get(market_id)
                        
                        size = float(pos_data.get("size") or pos_data.get("amount") or 0)
                        pw_avg = pos_data.get("avgPrice") or pos_data.get("initialPrice") or pos_data.get("averagePrice") or 0
                        avg_price = float(pw_avg)
                        
                        # ─── Outcome-to-Price Mapping ───
                        # NOTE: Polymarket API uses "curPrice" not "currentPrice"
                        current_price = float(pos_data.get("curPrice") or pos_data.get("currentPrice") or pos_data.get("price") or 0)
                        
                        if market_info:
                            # Use outcome-specific prices if available
                            if current_price < 0.001 and market_info.prices:
                                outcome_str = str(pos_data.get("outcome", "")).lower()
                                try:
                                    if "yes" in outcome_str or "up" in outcome_str or outcome_str == "1":
                                        current_price = market_info.prices[0] if len(market_info.prices) > 0 else 0.5
                                    elif "no" in outcome_str or "down" in outcome_str or outcome_str == "0":
                                        current_price = market_info.prices[1] if len(market_info.prices) > 1 else 0.5
                                    else:
                                        current_price = next((p for p in market_info.prices if p > 0), 0.5)
                                except:
                                    current_price = market_info.price
                            
                            # Handle Resolved Markets ($1 or $0)
                            if market_info.is_resolved:
                                outcome_idx = str(pos_data.get("outcome", ""))
                                winning_idx = str(market_info.winning_outcome or "")
                                if outcome_idx and winning_idx and outcome_idx == winning_idx:
                                    current_price = 1.0
                                elif outcome_idx and winning_idx:
                                    current_price = 0.0
                        
                        # P&L calculation
                        unrealized_pnl = float(pos_data.get("unrealizedPnl") or 0)
                        total_cost = size * avg_price
                        current_value = size * current_price
                        
                        if unrealized_pnl == 0 and size > 0:
                            unrealized_pnl = current_value - total_cost
                        else:
                            if current_value == 0 and unrealized_pnl != 0:
                                current_value = total_cost + unrealized_pnl
                        
                        outcome = str(pos_data.get("outcome") or "")
                        
                        position = PositionInfo(
                            market_id=str(market_id),
                            market_question=market_info.question if market_info else f"Market {market_id[:8]}",
                            token_id=str(pos_data.get("asset") or pos_data.get("asset_id") or pos_data.get("tokenId") or ""),
                            outcome=outcome,
                            size=size,
                            avg_price=avg_price,
                            current_price=current_price,
                            unrealized_pnl=unrealized_pnl,
                            realized_pnl=float(pos_data.get("realizedPnl") or pos_data.get("pnl") or 0),
                            total_cost=total_cost,
                            current_value=current_value
                        )
                        positions.append(position)
                    
                    return positions
                else:
                    logger.error(f"Failed to fetch positions: {response.status}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching wallet positions: {e}")
            return []
    
    # ─── Wallet Stats (Period-Aware) ────────────────────────────────────────
    async def get_wallet_stats(
        self,
        wallet_address: str,
        period: str = TimePeriod.ALL
    ) -> WalletStats:
        """
        Get comprehensive statistics for a wallet, filtered by time period.
        
        Args:
            wallet_address: The wallet address to get stats for.
            period: Time period filter - "1D", "1M", "1Y", or "ALL".
        """
        try:
            logger.info(f"🔍 Fetching stats for {wallet_address} [{period}]...")
            
            # Fetch all data in parallel
            trades_task = self.get_wallet_trades(wallet_address, limit=200)
            positions_task = self.get_wallet_positions(wallet_address)
            closed_task = self.get_wallet_closed_positions(wallet_address, limit=200)
            
            trades, positions, closed_positions = await asyncio.gather(
                trades_task, positions_task, closed_task
            )
            
            logger.info(f"📊 {len(trades)} trades, {len(positions)} open, {len(closed_positions)} closed")
            # ─── Apply Time Period Filter ───
            cutoff = TimePeriod.get_cutoff(period)
            
            if cutoff:
                # Filter trades by timestamp
                filtered_trades = [
                    t for t in trades
                    if t.timestamp.tzinfo and t.timestamp >= cutoff
                ]
                # Filter closed positions by timestamp
                filtered_closed = [
                    cp for cp in closed_positions
                    if cp.timestamp and cp.timestamp.tzinfo and cp.timestamp >= cutoff
                ]
            else:
                filtered_trades = trades
                filtered_closed = closed_positions
            
            # ─── Calculate Stats ───
            stats = WalletStats(
                wallet_address=wallet_address,
                trade_history=filtered_trades,
                positions=positions,
                closed_positions=filtered_closed,
                active_positions=len(positions),
                period=period
            )
            
            # Realized P&L from closed positions
            closed_pnl = sum(cp.realized_pnl for cp in filtered_closed)
            
            # Open positions P&L
            open_realized = sum(p.realized_pnl for p in positions)
            open_unrealized = sum(p.unrealized_pnl for p in positions)
            total_cost = sum(p.total_cost for p in positions)
            
            # Total P&L = Closed + Open
            stats.total_pnl = closed_pnl + open_realized + open_unrealized
            
            # Trade counts and volume
            if filtered_trades:
                stats.total_trades = len(filtered_trades)
                stats.total_volume = sum(t.amount for t in filtered_trades)
                winning = sum(
                    1 for t in filtered_trades
                    if (t.side == "SELL" and t.price > 0.5) or (t.side == "BUY" and t.price < 0.5)
                )
                stats.win_rate = (winning / stats.total_trades * 100) if stats.total_trades > 0 else 0
                stats.winning_trades = winning
                stats.losing_trades = stats.total_trades - winning
            else:
                stats.total_trades = len(positions) + len(filtered_closed)
                stats.total_volume = total_cost + sum(cp.size * cp.avg_price for cp in filtered_closed)
                # Win rate from closed positions
                if filtered_closed:
                    wins = sum(1 for cp in filtered_closed if cp.realized_pnl > 0)
                    stats.win_rate = (wins / len(filtered_closed) * 100)
                    stats.winning_trades = wins
                    stats.losing_trades = len(filtered_closed) - wins
                else:
                    stats.win_rate = 0.0
            
            # P&L percentage
            basis = stats.total_volume if stats.total_volume > 0 else total_cost
            if basis > 0:
                stats.pnl_percentage = (stats.total_pnl / basis) * 100
            
            # Best/worst trade (from closed positions for accuracy)
            if filtered_closed:
                pnls = [cp.realized_pnl for cp in filtered_closed]
                stats.best_trade = max(pnls)
                stats.worst_trade = min(pnls)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating wallet stats: {e}")
            return WalletStats(wallet_address=wallet_address, period=period)
    
    # ─── Market Info ────────────────────────────────────────────────────────
    async def get_market_info(self, market_id: str) -> Optional[MarketInfo]:
        """Get information about a specific market."""
        if not market_id:
            return None
        
        # Check cache
        if market_id in self._market_cache:
            return self._market_cache[market_id]
        
        try:
            # Primary: Search by conditionId
            url = f"{self.settings.gamma_api_url}/markets"
            params = {"conditionId": market_id}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        m_data = data[0]
                        prices_raw = m_data.get("outcomePrices", [])
                        prices = []
                        for p in prices_raw:
                            try:
                                prices.append(float(p))
                            except:
                                prices.append(0.0)
                        
                        market = MarketInfo(
                            market_id=str(m_data.get("id", market_id)),
                            question=m_data.get("question", ""),
                            description=m_data.get("description", ""),
                            end_date=self._parse_date(m_data.get("endDate")),
                            outcomes=m_data.get("outcomes", []),
                            tokens=m_data.get("tokens", []),
                            volume=float(m_data.get("volume", 0)),
                            liquidity=float(m_data.get("liquidity", 0)),
                            active=m_data.get("active", False),
                            price=prices[0] if prices else 0.5,
                            prices=prices,
                            is_resolved=m_data.get("closed", False) or m_data.get("resolved", False),
                            winning_outcome=str(m_data.get("winningOutcome", ""))
                        )
                        
                        self._market_cache[market_id] = market
                        return market

            # Fallback: Direct market lookup
            url = f"{self.settings.gamma_api_url}/markets/{market_id}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    prices_raw = data.get("outcomePrices", [])
                    prices = []
                    for p in prices_raw:
                        try:
                            prices.append(float(p))
                        except:
                            prices.append(0.0)
                    
                    market = MarketInfo(
                        market_id=market_id,
                        question=data.get("question", ""),
                        description=data.get("description", ""),
                        end_date=self._parse_date(data.get("endDate")),
                        outcomes=data.get("outcomes", []),
                        tokens=data.get("tokens", []),
                        volume=float(data.get("volume", 0)),
                        liquidity=float(data.get("liquidity", 0)),
                        active=data.get("active", False),
                        price=prices[0] if prices else 0.5,
                        prices=prices,
                        is_resolved=data.get("closed", False) or data.get("resolved", False),
                        winning_outcome=str(data.get("winningOutcome", ""))
                    )
                    self._market_cache[market_id] = market
                    return market
                    
        except Exception:
            pass
        
        return None
    
    # ─── Active Markets ─────────────────────────────────────────────────────
    async def get_active_markets(self, limit: int = 50) -> List[MarketInfo]:
        """Get list of currently active markets."""
        try:
            url = f"{self.settings.gamma_api_url}/markets"
            params = {
                "active": "true", 
                "closed": "false",
                "limit": limit, 
                "sort": "volume24hr:desc"
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    markets = []
                    
                    import json
                    for m in data:
                        token_ids = []
                        
                        # Try standard tokens field first
                        raw_tokens = m.get("tokens")
                        if raw_tokens:
                            for t in raw_tokens:
                                tid = t.get("token_id") or t.get("id")
                                if tid:
                                    token_ids.append(tid)
                        
                        # Fallback to clobTokenIds (often a JSON string in Gamma API)
                        if not token_ids:
                            clob_ids_raw = m.get("clobTokenIds")
                            if clob_ids_raw:
                                if isinstance(clob_ids_raw, str):
                                    try:
                                        token_ids = json.loads(clob_ids_raw)
                                    except:
                                        pass
                                elif isinstance(clob_ids_raw, list):
                                    token_ids = clob_ids_raw

                        market = MarketInfo(
                            market_id=m.get("conditionId", ""),
                            question=m.get("question", ""),
                            description=m.get("description", ""),
                            end_date=self._parse_date(m.get("endDate")),
                            outcomes=m.get("outcomes", []),
                            tokens=token_ids,
                            volume=float(m.get("volume", 0)),
                            liquidity=float(m.get("liquidity", 0)),
                            active=m.get("active", False)
                        )
                        markets.append(market)
                        self._market_cache[market.market_id] = market
                    
                    return markets
                    
        except Exception as e:
            logger.error(f"Error fetching active markets: {e}")
        
        return []
    
    # ─── Token Price ────────────────────────────────────────────────────────
    async def get_token_price(self, token_id: str) -> Optional[float]:
        """Get current price for a token."""
        try:
            url = f"{self.settings.clob_api_url}/price"
            params = {"token_id": token_id}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return float(data.get("price", 0))
                    
        except Exception as e:
            logger.error(f"Error fetching token price: {e}")
        
        return None
    
    # ─── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _parse_date(date_val) -> Optional[datetime]:
        """Safely parse a date value."""
        if not date_val:
            return None
        try:
            if isinstance(date_val, (int, float)):
                return datetime.fromtimestamp(date_val, tz=timezone.utc)
            return datetime.fromisoformat(str(date_val).replace('Z', '+00:00'))
        except:
            return None
