# 🤖 Polymarket Copy Trading Bot

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Mac-lightgrey.svg)

**Professional copy trading bot for Polymarket with zero-delay execution and a stunning dashboard!**

[Features](#features) • [Installation](#installation) • [Configuration](#configuration) • [Usage](#usage) • [Dashboard](#dashboard)

</div>

---

## ✨ Features

### 🎯 Copy Trading Engine
- **Zero-Delay WebSocket Monitoring** - Real-time trade detection via WebSocket
- **Multiple Copy Modes** - Proportional, fixed amount, or mirror copying
- **Smart Position Sizing** - Automatically scale positions based on your preferences  
- **Safety Limits** - Maximum trade amount limits to protect your capital
- **Auto-Reconnect** - Robust connection handling with automatic recovery

### 📊 Professional Dashboard
- **Real-time P&L Tracking** - Live profit/loss for both target and your account
- **Position Monitoring** - View all active positions with current prices
- **Trade History** - Complete log of all copied trades
- **Beautiful Dark Theme** - Premium glassmorphism design
- **Interactive Charts** - Visualize performance over time

### 🔧 Technical Features
- **Polymarket CLOB API** - Official API integration for reliable execution
- **WebSocket + REST Polling** - Dual monitoring for maximum reliability
- **Async Architecture** - High-performance async Python
- **MongoDB Support** - Optional trade history persistence
- **Configurable Everything** - Full control via environment variables

---

## 📦 Installation

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- A Polymarket account with funds
- API credentials from Polymarket

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/polymarket-copy-bot.git
cd polymarket-copy-bot
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
# Copy the example config
copy .env.example .env    # Windows
cp .env.example .env      # Linux/Mac

# Edit .env with your credentials
```

---

## ⚙️ Configuration

Edit the `.env` file with your credentials:

```env
# Your Polymarket Account
PRIVATE_KEY=your_wallet_private_key_here
API_KEY=your_api_key_here
API_SECRET=your_api_secret_here
API_PASSPHRASE=your_api_passphrase_here

# Target Wallet to Copy
TARGET_WALLET_ADDRESS=0x63ce342161250d705dc0b16df89036c8e5f9ba9a

# Trading Settings
COPY_MODE=proportional    # proportional, fixed, or mirror
SCALE_FACTOR=1.0          # 1.0 = same size, 0.5 = half size
FIXED_TRADE_AMOUNT=10.0   # USDC amount for fixed mode
MAX_TRADE_AMOUNT=100.0    # Maximum per trade (safety)

# Dashboard
THEME=dark                # dark or light
```

### Getting API Credentials

1. Go to [Polymarket](https://polymarket.com)
2. Connect your wallet
3. Navigate to Settings → API
4. Generate your API keys
5. Copy API Key, Secret, and Passphrase to `.env`

---

## 🚀 Usage

### GUI Dashboard Mode (Recommended)
```bash
python main.py
```
This opens the beautiful dashboard where you can:
- Start/stop the bot
- Monitor live P&L
- View positions and trade history
- Adjust settings

### CLI Mode
```bash
python main.py --cli
```
Run headless without GUI - perfect for servers.

### Verbose Logging
```bash
python main.py -v
python main.py --cli -v
```

---

## 🖥️ Dashboard

The dashboard provides a professional interface for monitoring your copy trading:

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   🎯 TARGET WALLET              👤 YOUR ACCOUNT              ║
║   ─────────────────             ─────────────                ║
║   P&L: +$1,234.56              P&L: +$987.65                ║
║   Win Rate: 68%                 Copied: 45 trades            ║
║   Volume: $12,345              Success: 98%                  ║
║                                                               ║
║   📜 ACTIVITY LOG                                             ║
║   ─────────────                                               ║
║   14:23:05 | BUY  0.5000 @ $0.65 | ✅ Filled                ║
║   14:21:32 | SELL 0.2500 @ $0.78 | ✅ Filled                ║
║   14:18:17 | BUY  1.0000 @ $0.42 | ✅ Filled                ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

### Dashboard Features:
- **🎯 Target Wallet Panel** - Shows the wallet you're copying
- **👤 Your Account Panel** - Your positions and P&L
- **📜 Activity Log** - Real-time trade copy log
- **⚙️ Settings** - Adjust copy parameters on the fly
- **▶️/⏹️ Controls** - Start and stop with one click

---

## 📁 Project Structure

```
PolyMArket CopyTradingBot/
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── .env.example              # Configuration template
│
├── src/
│   ├── __init__.py
│   ├── config.py             # Settings management
│   │
│   ├── api/                  # API clients
│   │   ├── __init__.py
│   │   ├── polymarket_client.py   # CLOB trading client
│   │   ├── data_fetcher.py        # Market data & stats
│   │   └── trade_monitor.py       # WebSocket monitor
│   │
│   ├── engine/               # Core logic
│   │   ├── __init__.py
│   │   └── copy_engine.py    # Copy trading engine
│   │
│   └── gui/                  # Dashboard
│       ├── __init__.py
│       ├── theme.py          # Colors & styling
│       ├── components.py     # UI components
│       └── main_dashboard.py # Main window
│
└── README.md
```

---

## 🔐 Security Notes

⚠️ **IMPORTANT: Keep your private key secure!**

- Never share your `.env` file
- Never commit `.env` to git
- Use a dedicated wallet for trading
- Start with small amounts to test
- Set appropriate MAX_TRADE_AMOUNT limits

---

## 🛠️ Troubleshooting

### "Failed to initialize Polymarket client"
- Check your API credentials in `.env`
- Ensure your wallet has USDC balance
- Verify you're on Polygon network

### "WebSocket connection closed"
- Normal during maintenance - bot auto-reconnects
- Check your internet connection
- Polymarket may be under heavy load

### "Copy failed: Insufficient balance"
- Add more USDC to your Polymarket wallet
- Reduce SCALE_FACTOR or FIXED_TRADE_AMOUNT

---

## 📝 License

MIT License - feel free to use and modify!

---

## 🙏 Disclaimer

⚠️ **This bot is for educational purposes only.**

Trading on Polymarket involves risk. Past performance does not guarantee future results. Never trade with money you can't afford to lose. The developers are not responsible for any financial losses incurred from using this software.

---

<div align="center">

**Built with ❤️ for the Polymarket community**

[Report Bug](https://github.com/yourusername/polymarket-copy-bot/issues) • [Request Feature](https://github.com/yourusername/polymarket-copy-bot/issues)

</div>
