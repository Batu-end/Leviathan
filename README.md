# Leviathan

Leviathan is designed to be a system to track whale movements in crypto markets.

A "whale" is a customer who spends who spends a lot financially on a product or service.
This could be video games, casinos and many more realms of endeavor.
In the realm of trading, crypto whales are the people who have tens of millions of dollars
to invest in an asset. Tracking the movements of these people is often important, since they
can be a potential signal.

# Setup Guide

### 🤖 **New Slash Commands:**
- `/whale_check` - Check recent whale activity with **transaction type analysis**
- `/whale_config` - Configure detection thresholds 
- `/whale_stats` - View system statistics and status
- `/whale_prices` - Get current BTC/ETH prices with whale thresholds

### 🧠 **Smart Transaction Classification:**
- **🏦 Exchange Operations**: Deposits, withdrawals, inter-exchange transfers
- **� Wallet Activities**: Personal transfers, consolidations, distributions  
- **🔒 Privacy Transactions**: Mixing service detection
- **📊 Pattern Analysis**: Simple transfers, complex transactions, fund movements
- **🏷️ Address Classification**: Exchange wallets, personal wallets, cold storage

### �🔄 **Background Monitoring:**
- **Auto-scanning intervals** for whale activity
- **Enhanced alerts** with transaction type and source/destination info
- **Real-time price tracking** for BTC and ETH
- **Multi-source monitoring**: On-chain + exchanges + mempool

### 📊 **Data Sources Integrated:**
- **Bitcoin**: Blockchain.info (transactions + mempool) with full analysis
- **Ethereum**: Etherscan API with classification ready
- **US Exchanges**: Coinbase Pro, Gemini order book monitoring
- **Prices**: CoinGecko real-time data

## 🚀 Setup Instructions

### 1. Configure Environment Variables


### 2. Bot Permissions Required
Your Discord bot needs these permissions:
- ✅ `Send Messages`
- ✅ `Use Slash Commands` 
- ✅ `Embed Links`
- ✅ `Read Message History`

## Usage & Commands

### Quick Whale Check
```
/whale_check
```
**Returns:**
- Current BTC/ETH prices
- Number of large transactions found
- Recent whale activity details
- Exchange order book analysis

### Configure Thresholds
```
/whale_config btc_threshold:2000000 eth_threshold:1000000
```
**Changes detection to $2M for BTC, $1M for ETH**

### View Statistics
```
/whale_stats
```
**Shows:**
- Current thresholds
- System status
- Data sources
- Session statistics

### Quick Price Check
```
/whale_prices
```
**Returns:**
- Current BTC/ETH prices
- Whale thresholds in native currency

## 🚨 Automatic Alerts

Your bot will now automatically:

1. **Scan every x seconds** for whale activity
2. **Post alerts** to your server when large transactions are detected
3. **Show transaction details** including amounts and values
4. **Track both pending and confirmed** transactions

### Sample Alert:
```
🚨 WHALE ALERT 🚨
Large BTC Transaction Detected

💰 Amount: 127.45 BTC
💵 Value: $14,592,384.50
🔗 Hash: a1b2c3d4e5f6...
```

## 🔧 Customization

### Change Monitoring Frequency
In `bot.py`, modify this line:
```python
@tasks.loop(minutes=10)  # Change to your preferred interval
```

### Adjust Detection Thresholds
Use `/whale_config` command or modify defaults in `bot.py`:
```python
whale_tracker = WhaleTracker(
    btc_threshold_usd=2_000_000,  # $2M for BTC
    eth_threshold_usd=1_000_000,  # $1M for ETH
)
```

## 🎯 What's Working Now

✅ **Bitcoin whale detection** - Live transaction monitoring  
✅ **Exchange order monitoring** - Large Binance orders  
✅ **Real-time price tracking** - BTC/ETH prices  
✅ **Discord integration** - Slash commands + auto alerts  
✅ **Background monitoring** - Continuous scanning  
✅ **Error handling** - Graceful failure recovery  
