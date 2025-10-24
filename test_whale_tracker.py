#!/usr/bin/env python3
"""
Test script for the whale tracker system
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher.transactions import WhaleTracker, BitcoinWhaleMonitor, EthereumWhaleMonitor, ExchangeMonitor
import aiohttp

async def test_whale_tracker():
    """Test the whale tracking system with sample data"""
    
    print("🐋 Testing Whale Tracker System")
    print("=" * 50)
    
    # Initialize with lower thresholds for testing
    api_keys = {
        'etherscan': 'demo',  # Use demo key for testing
    }
    
    whale_tracker = WhaleTracker(
        btc_threshold_usd=10_000,    # $10K for testing (much lower)
        eth_threshold_usd=5_000,     # $5K for testing
        api_keys=api_keys
    )
    
    print("✓ Whale tracker initialized")
    print(f"  - BTC threshold: ${whale_tracker.btc_threshold:,}")
    print(f"  - ETH threshold: ${whale_tracker.eth_threshold:,}")
    
    # Test Bitcoin monitor
    btc_monitor = BitcoinWhaleMonitor(whale_tracker)
    eth_monitor = EthereumWhaleMonitor(whale_tracker)
    exchange_monitor = ExchangeMonitor(whale_tracker)
    
    print("\n📊 Testing price fetching...")
    
    async with aiohttp.ClientSession() as session:
        # Test price fetching
        btc_price = await btc_monitor.get_btc_price(session)
        eth_price = await eth_monitor.get_eth_price(session)
        
        print(f"✓ BTC Price: ${btc_price:,.2f}")
        print(f"✓ ETH Price: ${eth_price:,.2f}")
        
        print("\n🔍 Testing Bitcoin transaction monitoring...")
        btc_transactions = await btc_monitor.fetch_large_transactions(session)
        print(f"✓ Found {len(btc_transactions)} large BTC transactions")
        
        if btc_transactions:
            for tx in btc_transactions[:3]:  # Show first 3
                print(f"  - {tx['btc_amount']:.2f} BTC (${tx['usd_value']:,.2f})")
        
        print("\n🔍 Testing Bitcoin mempool monitoring...")
        btc_mempool = await btc_monitor.monitor_mempool(session)
        print(f"✓ Found {len(btc_mempool)} large pending BTC transactions")
        
        print("\n🔍 Testing US exchange order book monitoring...")
        
        # Test US exchanges
        coinbase_btc = await exchange_monitor.monitor_coinbase_pro_orderbook(session, 'BTC-USD')
        coinbase_eth = await exchange_monitor.monitor_coinbase_pro_orderbook(session, 'ETH-USD')
        kraken_btc = await exchange_monitor.monitor_kraken_orderbook(session, 'BTCUSD')
        gemini_btc = await exchange_monitor.monitor_gemini_orderbook(session, 'btcusd')
        
        total_btc_orders = len(coinbase_btc) + len(kraken_btc) + len(gemini_btc)
        total_eth_orders = len(coinbase_eth)
        
        print(f"✓ Found {len(coinbase_btc)} large BTC orders on Coinbase Pro")
        print(f"✓ Found {len(kraken_btc)} large BTC orders on Kraken")
        print(f"✓ Found {len(gemini_btc)} large BTC orders on Gemini")
        print(f"✓ Found {len(coinbase_eth)} large ETH orders on Coinbase Pro")
        print(f"✓ Total: {total_btc_orders} BTC orders, {total_eth_orders} ETH orders")
        
        # Show sample orders from all exchanges
        all_btc_orders = coinbase_btc + kraken_btc + gemini_btc
        all_eth_orders = coinbase_eth
        
        if all_btc_orders:
            print("\nSample BTC orders:")
            for order in all_btc_orders[:3]:
                exchange = order['exchange'].replace('_', ' ').title()
                print(f"  - {exchange}: {order['side'].upper()} {order['quantity']:.2f} BTC @ ${order['price']:,.2f} = ${order['usd_value']:,.2f}")
        
        if all_eth_orders:
            print("\nSample ETH orders:")
            for order in all_eth_orders[:3]:
                exchange = order['exchange'].replace('_', ' ').title()
                print(f"  - {exchange}: {order['side'].upper()} {order['quantity']:.2f} ETH @ ${order['price']:,.2f} = ${order['usd_value']:,.2f}")

    print("\n✅ Whale tracker test completed successfully!")
    print("\nTo run the full system:")
    print("1. Get API keys (Etherscan, etc.)")
    print("2. Update config.env with your keys")
    print("3. Run: python -m fetcher.transactions")

if __name__ == "__main__":
    asyncio.run(test_whale_tracker())