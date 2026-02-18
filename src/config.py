"""
Configuration Management
========================
Handles all environment variables and settings for the copy trading bot.
Supports both Polymarket proxy wallets and MetaMask/EOA wallets.
"""

import os
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Wallet & API Credentials
    private_key: str = Field(default="", description="Your wallet private key")
    api_key: str = Field(default="", description="Polymarket API key")
    api_secret: str = Field(default="", description="Polymarket API secret")
    api_passphrase: str = Field(default="", description="Polymarket API passphrase")
    
    # Wallet Type: 'metamask' for EOA (signature_type=0) or 'polymarket' for proxy wallet
    wallet_type: Literal["metamask", "polymarket"] = Field(
        default="metamask",
        description="Wallet type: metamask (EOA) or polymarket (proxy)"
    )
    
    # Funder address (for MetaMask mode, usually same as your wallet address)
    funder_address: str = Field(
        default="",
        description="Funder address for MetaMask mode (leave empty to use wallet address)"
    )
    
    # Target Wallet
    target_wallet_address: str = Field(
        default="0x63ce342161250d705dc0b16df89036c8e5f9ba9a",
        description="Wallet address to copy trades from"
    )
    
    # Trading Settings
    copy_mode: Literal["proportional", "fixed"] = Field(
        default="proportional",
        description="Copy mode: proportional or fixed amount"
    )
    scale_factor: float = Field(
        default=1.0,
        description="Scale factor for proportional copying (1.0 = same size)"
    )
    fixed_trade_amount: float = Field(
        default=10.0,
        description="Fixed USDC amount per trade if using fixed mode"
    )
    max_trade_amount: float = Field(
        default=100.0,
        description="Maximum amount per single trade (safety limit)"
    )
    
    # MongoDB
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB connection URI"
    )
    mongodb_database: str = Field(
        default="polymarket_copy_bot",
        description="MongoDB database name"
    )
    
    # Dashboard
    dashboard_refresh_rate: int = Field(
        default=1000,
        description="Dashboard refresh rate in milliseconds"
    )
    theme: Literal["dark", "light"] = Field(
        default="dark",
        description="Dashboard theme"
    )
    
    # Default time period for dashboard stats
    default_period: str = Field(
        default="ALL",
        description="Default time period filter: 1D, 1M, 1Y, ALL"
    )
    
    # Network
    rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon RPC URL"
    )
    clob_api_url: str = Field(
        default="https://clob.polymarket.com",
        description="Polymarket CLOB API URL"
    )
    gamma_api_url: str = Field(
        default="https://gamma-api.polymarket.com",
        description="Polymarket Gamma API URL"
    )
    data_api_url: str = Field(
        default="https://data-api.polymarket.com",
        description="Polymarket Data API URL"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get the global settings instance."""
    return settings


def validate_settings() -> tuple[bool, list[str]]:
    """Validate that all required settings are configured."""
    errors = []
    
    if not settings.private_key:
        errors.append("PRIVATE_KEY is required (MetaMask private key)")
    
    # API keys are optional for MetaMask mode (auto-derived)
    if settings.wallet_type == "polymarket":
        if not settings.api_key:
            errors.append("API_KEY is required for Polymarket proxy wallet mode")
        if not settings.api_secret:
            errors.append("API_SECRET is required for Polymarket proxy wallet mode")
        if not settings.api_passphrase:
            errors.append("API_PASSPHRASE is required for Polymarket proxy wallet mode")
    
    if not settings.target_wallet_address:
        errors.append("TARGET_WALLET_ADDRESS is required")
        
    return len(errors) == 0, errors
