# 🤖 Multi-Chain Token Launcher Bot

Real tools. Real money. One seed phrase controls all chains.

## 🚀 Features

| Feature | Tool Used |
|---------|-----------|
| **Token Creation** | SPL Token Program |
| **Swaps** | Jupiter API v1 |
| **Price Data** | Jupiter Price API v2 |
| **Holder Counting** | Helius RPC + getProgramAccounts |
| **Pool Creation** | Smithii Tools (Raydium) |
| **Volume Boosting** | Multi-wallet rotation + Jupiter |
| **Profit Calc** | Real AMM constant-product math |
| **Multi-Chain** | Solana + ETH/BSC/Base/Arbitrum |

## 📊 The Math

**Scenario:** You buy $11, 10 people buy $40 each, you hold 90%, you dump.

| | Amount |
|---|---|
| You put in | $11 + 2 SOL for LP |
| 10 buyers put in | $400 total |
| Pool grows to | ~4.67 SOL ($700) |
| You dump 900M tokens | |
| **You receive** | **~$668** |
| **Your net profit** | **~$368** |
| **If free-minted** | **$668 pure profit** |
| Buyers left with | ~$2 (99.5% loss) |

## 🔑 Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
python app.py
```

## 🎮 Telegram Buttons

```
┌─────────────────────────────────────────┐
│  🤖 MyToken Multi-Chain Bot             │
│  💼 Sol: 7x9A... | ETH: 0x3f2...        │
│  💰 2.45 SOL                            │
├─────────────────────────────────────────┤
│  [🚀 LAUNCH]        [💰 WALLET]         │
│  [📊 ANALYTICS]     [🔴 SELL]           │
│  [🟢 BUY]           [💧 LIQUIDITY]      │
│  [📈 VOLUME BOT]    [🧮 PROFIT CALC]    │
│  [⚙️ SETTINGS]                          │
└─────────────────────────────────────────┘
```

## 🚀 Deploy to Render

1. Push to GitHub
2. Connect repo at https://dashboard.render.com/
3. Use `render.yaml` (already included)
4. Add environment variables in dashboard
5. Done

## ⏰ UptimeRobot

- URL: `https://your-app.onrender.com/health`
- Interval: 5 minutes
- Keeps free tier awake

## ⚠️ Legal Notice

This tool is for educational purposes. Rug pulls are securities fraud.
