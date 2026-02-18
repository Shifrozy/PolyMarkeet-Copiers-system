"""
Polymarket CLOB Client
======================
Client for interacting with Polymarket's CLOB API.
Supports both Polymarket proxy wallets and MetaMask/EOA wallets.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum

import requests
import aiohttp
from eth_account import Account
from web3 import Web3

from src.config import settings, get_settings

logger = logging.getLogger(__name__)

# Polygon Mainnet
CHAIN_ID = 137
# Polymarket CTF Exchange contract on Polygon
CTF_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982e"
# Polymarket Neg Risk CTF Exchange
NEG_RISK_CTF_EXCHANGE = "0xC5d563A36AE78145C45a50134d48A1215220f80a"
# USDC on Polygon
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"


class Side(Enum):
    """Trade side enumeration."""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class TradeOrder:
    """Represents a trade order."""
    token_id: str
    side: Side
    size: float
    price: float
    market_id: str
    market_question: str


@dataclass
class OrderResult:
    """Result of an order placement."""
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    transaction_hash: Optional[str] = None


class PolymarketClient:
    """
    Client for Polymarket CLOB API.
    
    Supports two wallet types:
    - 'polymarket': Uses Polymarket's proxy wallet system
    - 'metamask': Uses direct EOA (MetaMask) wallet with signature_type=0
    """
    
    def __init__(self):
        """Initialize the Polymarket client."""
        self.settings = get_settings()
        self.clob_client = None
        self._is_initialized = False
        self._wallet_address = None
        self._web3: Optional[Web3] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Balance cache to avoid rate limits
        self._balance_cache: float = 0.0
        self._last_balance_check: float = 0
        self._account = None
        
    async def initialize(self) -> bool:
        """Initialize the CLOB client."""
        if self._is_initialized:
            return True
            
        try:
            logger.info("🚀 Initializing Polymarket CLOB client...")
            
            # Start session
            if not self._session or self._session.closed:
                self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
                
            # Connect to Polygon RPC
            self._web3 = Web3(Web3.HTTPProvider(self.settings.rpc_url))
            if not self._web3.is_connected():
                logger.warning("⚠️ Could not connect to Polygon RPC, trying fallback...")
                self._web3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
            
            # Derive wallet from private key
            pk = self.settings.private_key
            if pk:
                if pk.startswith("0x"):
                    pk = pk[2:]
                try:
                    self._account = Account.from_key(pk)
                    self._wallet_address = self._account.address
                    logger.info(f"👛 Wallet: {self._wallet_address}")
                except Exception as e:
                    logger.error(f"Invalid private key: {e}")
            
            # Import py-clob-client
            try:
                from py_clob_client.client import ClobClient
                from py_clob_client.clob_types import ApiCreds
                
                wallet_type = getattr(self.settings, 'wallet_type', 'metamask')
                
                if wallet_type == "metamask":
                    logger.info("🦊 Initializing MetaMask mode...")
                    funder = getattr(self.settings, 'funder_address', '') or self._wallet_address
                    
                    if self.settings.api_key and self.settings.api_secret and self.settings.api_passphrase:
                        creds = ApiCreds(
                            api_key=self.settings.api_key,
                            api_secret=self.settings.api_secret,
                            api_passphrase=self.settings.api_passphrase
                        )
                        self.clob_client = ClobClient(
                            host=self.settings.clob_api_url,
                            key=self.settings.private_key,
                            creds=creds,
                            chain_id=CHAIN_ID,
                            signature_type=0, 
                            funder=funder
                        )
                    else:
                        try:
                            self.clob_client = ClobClient(
                                host=self.settings.clob_api_url,
                                key=self.settings.private_key,
                                chain_id=CHAIN_ID,
                                signature_type=0,
                                funder=funder
                            )
                            api_creds = self.clob_client.create_or_derive_api_creds()
                            self.clob_client.set_api_creds(api_creds)
                            logger.info("✅ EOA API credentials linked successfully!")
                        except Exception as e:
                            logger.warning(f"⚠️ EOA auth failed: {e}")
                            self.clob_client = ClobClient(
                                host=self.settings.clob_api_url,
                                key=self.settings.private_key,
                                chain_id=CHAIN_ID,
                                signature_type=1,
                                funder=funder
                            )
                            api_creds = self.clob_client.create_or_derive_api_creds()
                            self.clob_client.set_api_creds(api_creds)
                else:
                    logger.info("🏦 Using Polymarket proxy wallet mode (signature_type=1)")
                    creds = ApiCreds(
                        api_key=self.settings.api_key,
                        api_secret=self.settings.api_secret,
                        api_passphrase=self.settings.api_passphrase
                    )
                    self.clob_client = ClobClient(
                        host=self.settings.clob_api_url,
                        key=self.settings.private_key,
                        creds=creds,
                        chain_id=CHAIN_ID
                    )
                
            except ImportError:
                logger.warning("⚠️ py-clob-client not installed. Trading features disabled.")
            
            self._is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize: {e}")
            return False
    
    async def place_order(self, order: TradeOrder) -> OrderResult:
        """Place an order on Polymarket."""
        if not self._is_initialized or not self.clob_client:
            return OrderResult(success=False, error="Client not initialized")
        
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY, SELL
            
            logger.info(f"📤 Placing {order.side.value} order: {order.size} @ {order.price}")
            
            side = BUY if order.side == Side.BUY else SELL
            
            order_args = OrderArgs(
                token_id=order.token_id,
                price=order.price,
                size=order.size,
                side=side,
                fee_rate_bps=0
            )
            
            # Create and sign order
            signed_order = self.clob_client.create_order(order_args)
            
            # Submit order
            from py_clob_client.clob_types import OrderType
            response = self.clob_client.post_order(signed_order, OrderType.GTC)
            
            if response.get("success"):
                order_id = response.get("orderID")
                logger.info(f"✅ Order placed! ID: {order_id}")
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    transaction_hash=response.get("transactionHash")
                )
            else:
                error = response.get("errorMsg", "Unknown error")
                logger.error(f"❌ Order failed: {error}")
                return OrderResult(success=False, error=error)
                
        except Exception as e:
            logger.error(f"❌ Order error: {e}")
            return OrderResult(success=False, error=str(e))
    
    async def place_market_order(
        self,
        token_id: str,
        side: Side,
        amount: float,
        market_id: str = "",
        market_question: str = ""
    ) -> OrderResult:
        """Place a market order (at best available price)."""
        try:
            price = await self.get_best_price(token_id, side)
            
            if price is None:
                return OrderResult(success=False, error="Could not get market price")
            
            size = amount / price if side == Side.BUY else amount
            
            order = TradeOrder(
                token_id=token_id,
                side=side,
                size=size,
                price=price,
                market_id=market_id,
                market_question=market_question
            )
            
            return await self.place_order(order)
            
        except Exception as e:
            return OrderResult(success=False, error=str(e))
    
    async def get_best_price(self, token_id: str, side: Side) -> Optional[float]:
        """Get the best available price for a token."""
        try:
            response = requests.get(
                f"{self.settings.clob_api_url}/book",
                params={"token_id": token_id},
                timeout=5
            )
            
            if response.status_code == 200:
                book = response.json()
                
                if side == Side.BUY:
                    asks = book.get("asks", [])
                    if asks:
                        return float(asks[0]["price"])
                else:
                    bids = book.get("bids", [])
                    if bids:
                        return float(bids[0]["price"])
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting best price: {e}")
            return None
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions for the connected wallet."""
        if not self._is_initialized:
            return []
        
        try:
            response = requests.get(
                f"{self.settings.clob_api_url}/data/positions",
                headers=self._get_auth_headers(),
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            return []
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return []
    
    async def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open orders."""
        if not self._is_initialized or not self.clob_client:
            return []
        
        try:
            response = self.clob_client.get_order()
            return response if response else []
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if not self._is_initialized or not self.clob_client:
            return False
        
        try:
            response = self.clob_client.cancel(order_id)
            return response.get("canceled", False)
        except Exception as e:
            logger.error(f"Error canceling order: {e}")
            return False
    
    async def get_balance(self) -> float:
        """Get USDC balance for the connected wallet with caching."""
        if not self._is_initialized:
            return 0.0
            
        import time
        now = time.time()
        # Cache balance for 10 seconds to avoid RPC rate limits
        if now - self._last_balance_check < 10:
            return self._balance_cache
        
        try:
            # Try CLOB API first (Async)
            async with self._session.get(
                f"{self.settings.clob_api_url}/data/balance",
                headers=self._get_auth_headers()
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self._balance_cache = float(data.get("balance", 0))
                    self._last_balance_check = now
                    return self._balance_cache
            
            # Fallback: Read USDC balance directly from Polygon
            if self._web3 and self._wallet_address:
                usdc_abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                            "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                            "type": "function"}]
                usdc = self._web3.eth.contract(
                    address=Web3.to_checksum_address(USDC_ADDRESS),
                    abi=usdc_abi
                )
                
                # Use a loop for simple retry on blockchain calls
                for _ in range(2):
                    try:
                        balance_raw = usdc.functions.balanceOf(
                            Web3.to_checksum_address(self._wallet_address)
                        ).call()
                        self._balance_cache = balance_raw / 1e6
                        self._last_balance_check = now
                        return self._balance_cache
                    except Exception as rpc_e:
                        if "rate limit" in str(rpc_e).lower():
                            await asyncio.sleep(1)
                            continue
                        raise rpc_e
            
            return self._balance_cache
            
        except Exception as e:
            if "rate limit" not in str(e).lower():
                logger.error(f"Error getting balance: {e}")
            return self._balance_cache
    
    async def check_wallet_ready(self) -> Dict[str, Any]:
        """
        Check if the MetaMask wallet is fully ready for trading.
        Returns a detailed status report:
        {
            "ready": bool,
            "usdc_balance": float,
            "matic_balance": float,
            "usdc_approved": bool,
            "issues": [str],
            "recommendations": [str]
        }
        """
        result = {
            "ready": False,
            "usdc_balance": 0.0,
            "matic_balance": 0.0,
            "usdc_approved": False,
            "issues": [],
            "recommendations": []
        }
        
        if not self._is_initialized or not self._web3 or not self._wallet_address:
            result["issues"].append("Client not initialized. Set PRIVATE_KEY in .env")
            return result
        
        try:
            wallet = Web3.to_checksum_address(self._wallet_address)
            
            # ─── 1. Check MATIC/POL balance (for gas) ───
            try:
                matic_wei = self._web3.eth.get_balance(wallet)
                result["matic_balance"] = float(Web3.from_wei(matic_wei, 'ether'))
                
                if result["matic_balance"] < 0.01:
                    result["issues"].append(
                        f"MATIC balance too low: {result['matic_balance']:.6f} MATIC"
                    )
                    result["recommendations"].append(
                        "Send at least 0.5 MATIC (POL) to your wallet for gas fees. "
                        "You can bridge from Ethereum or buy on Polygon directly."
                    )
            except Exception as e:
                result["issues"].append(f"Cannot check MATIC balance: {e}")
            
            # ─── 2. Check USDC balance ───
            try:
                usdc_abi = [
                    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                     "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                     "type": "function"},
                    {"constant": True,
                     "inputs": [
                         {"name": "_owner", "type": "address"},
                         {"name": "_spender", "type": "address"}
                     ],
                     "name": "allowance",
                     "outputs": [{"name": "remaining", "type": "uint256"}],
                     "type": "function"}
                ]
                usdc = self._web3.eth.contract(
                    address=Web3.to_checksum_address(USDC_ADDRESS),
                    abi=usdc_abi
                )
                
                balance_raw = usdc.functions.balanceOf(wallet).call()
                result["usdc_balance"] = balance_raw / 1e6  # USDC = 6 decimals
                
                if result["usdc_balance"] < 1.0:
                    result["issues"].append(
                        f"USDC balance too low: ${result['usdc_balance']:.2f}"
                    )
                    result["recommendations"].append(
                        "Send USDC to your wallet on Polygon network. "
                        "You can bridge from Ethereum using Polygon Bridge or buy directly. "
                        "Important: Must be USDC on Polygon, not Ethereum!"
                    )
                
                # ─── 3. Check USDC approval for CTF Exchange ───
                ctf_address = Web3.to_checksum_address(CTF_EXCHANGE)
                allowance = usdc.functions.allowance(wallet, ctf_address).call()
                allowance_usdc = allowance / 1e6
                
                # Consider approved if allowance > 1M USDC (unlimited approval)
                if allowance_usdc > 1_000_000:
                    result["usdc_approved"] = True
                elif allowance_usdc > result["usdc_balance"]:
                    result["usdc_approved"] = True
                else:
                    result["usdc_approved"] = False
                    result["issues"].append(
                        f"USDC not approved for Polymarket Exchange (allowance: ${allowance_usdc:.2f})"
                    )
                    result["recommendations"].append(
                        "Run the USDC approval transaction. The bot can do this "
                        "automatically — it's a one-time gas fee (~$0.001 on Polygon)."
                    )
                    
                # Also check Neg Risk CTF Exchange approval
                neg_risk_address = Web3.to_checksum_address(NEG_RISK_CTF_EXCHANGE)
                neg_allowance = usdc.functions.allowance(wallet, neg_risk_address).call()
                if neg_allowance / 1e6 < 1_000_000 and neg_allowance / 1e6 < result["usdc_balance"]:
                    result["recommendations"].append(
                        "Also approve USDC for the Neg Risk Exchange for full market coverage."
                    )
                    
            except Exception as e:
                result["issues"].append(f"Cannot check USDC: {e}")
            
            # ─── Final verdict ───
            result["ready"] = len(result["issues"]) == 0
            
        except Exception as e:
            result["issues"].append(f"Wallet check failed: {e}")
        
        return result
    
    async def approve_usdc(self, unlimited: bool = True) -> Dict[str, Any]:
        """
        Approve USDC spending for Polymarket Exchange contracts.
        This is a one-time on-chain transaction (costs ~$0.001 in MATIC gas).
        
        Args:
            unlimited: If True, approve max uint256 (standard practice).
                       If False, approve only current USDC balance.
        
        Returns:
            {"success": bool, "tx_hash": str, "error": str}
        """
        if not self._web3 or not self._account:
            return {"success": False, "tx_hash": None, "error": "Web3 not initialized"}
        
        try:
            wallet = Web3.to_checksum_address(self._wallet_address)
            
            # ERC-20 approve ABI
            approve_abi = [{
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            }]
            
            usdc = self._web3.eth.contract(
                address=Web3.to_checksum_address(USDC_ADDRESS),
                abi=approve_abi
            )
            
            # Max approval (standard for DeFi)
            if unlimited:
                amount = 2**256 - 1  # Max uint256
            else:
                # Approve just the current balance
                bal_abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                           "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                           "type": "function"}]
                usdc_bal = self._web3.eth.contract(
                    address=Web3.to_checksum_address(USDC_ADDRESS), abi=bal_abi
                )
                amount = usdc_bal.functions.balanceOf(wallet).call()
            
            results = {}
            
            # ─── Approve CTF Exchange ───
            logger.info("🔐 Approving USDC for Polymarket CTF Exchange...")
            nonce = self._web3.eth.get_transaction_count(wallet)
            gas_price = self._web3.eth.gas_price
            
            tx = usdc.functions.approve(
                Web3.to_checksum_address(CTF_EXCHANGE), amount
            ).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': 60000,
                'chainId': CHAIN_ID
            })
            
            signed_tx = self._web3.eth.account.sign_transaction(tx, self._account.key)
            tx_hash = self._web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            receipt = self._web3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt['status'] == 1:
                logger.info(f"✅ CTF Exchange approved! TX: {tx_hash.hex()}")
                results["ctf_exchange"] = {"success": True, "tx_hash": tx_hash.hex()}
            else:
                logger.error("❌ CTF Exchange approval failed!")
                results["ctf_exchange"] = {"success": False, "tx_hash": tx_hash.hex()}
            
            # ─── Approve Neg Risk CTF Exchange ───
            logger.info("🔐 Approving USDC for Neg Risk CTF Exchange...")
            nonce += 1
            
            tx2 = usdc.functions.approve(
                Web3.to_checksum_address(NEG_RISK_CTF_EXCHANGE), amount
            ).build_transaction({
                'from': wallet,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': 60000,
                'chainId': CHAIN_ID
            })
            
            signed_tx2 = self._web3.eth.account.sign_transaction(tx2, self._account.key)
            tx_hash2 = self._web3.eth.send_raw_transaction(signed_tx2.raw_transaction)
            receipt2 = self._web3.eth.wait_for_transaction_receipt(tx_hash2, timeout=60)
            
            if receipt2['status'] == 1:
                logger.info(f"✅ Neg Risk Exchange approved! TX: {tx_hash2.hex()}")
                results["neg_risk_exchange"] = {"success": True, "tx_hash": tx_hash2.hex()}
            else:
                logger.error("❌ Neg Risk Exchange approval failed!")
                results["neg_risk_exchange"] = {"success": False, "tx_hash": tx_hash2.hex()}
            
            all_success = all(v["success"] for v in results.values())
            return {
                "success": all_success,
                "details": results,
                "error": None if all_success else "Some approvals failed"
            }
            
        except Exception as e:
            logger.error(f"❌ Approval error: {e}")
            return {"success": False, "tx_hash": None, "error": str(e)}
    
    async def get_matic_balance(self) -> float:
        """Get MATIC/POL balance for gas fees."""
        if not self._web3 or not self._wallet_address:
            return 0.0
        try:
            wallet = Web3.to_checksum_address(self._wallet_address)
            wei = self._web3.eth.get_balance(wallet)
            return float(Web3.from_wei(wei, 'ether'))
        except Exception as e:
            logger.error(f"Error getting MATIC balance: {e}")
            return 0.0
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests."""
        if self.clob_client and self.clob_client.creds:
            return {
                "POLY_API_KEY": self.clob_client.creds.api_key,
                "POLY_API_SECRET": self.clob_client.creds.api_secret,
                "POLY_API_PASSPHRASE": self.clob_client.creds.api_passphrase
            }
        
        return {
            "POLY_API_KEY": self.settings.api_key,
            "POLY_API_SECRET": self.settings.api_secret,
            "POLY_API_PASSPHRASE": self.settings.api_passphrase
        }
    
    @property
    def wallet_address(self) -> Optional[str]:
        """Get the connected wallet address."""
        return self._wallet_address
    
    @property
    def is_initialized(self) -> bool:
        """Check if client is initialized."""
        return self._is_initialized
