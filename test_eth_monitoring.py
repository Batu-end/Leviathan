#!/usr/bin/env python3
"""
Quick test to verify ETH monitoring is working
"""

import asyncio
import sys
import os
import aiohttp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher.transactions import WhaleTracker, EthereumWhaleMonitor

async def test_eth_monitoring():
    """Test Ethereum monitoring specifically"""
    
    print("🔍 Testing Ethereum Whale Monitoring")
    print("=" * 50)
    
    # Load Etherscan API key from .env
    from dotenv import load_dotenv
    load_dotenv()
    
    etherscan_key = os.getenv('ETHERSCAN_API_KEY')
    
    if not etherscan_key or etherscan_key == 'demo':
        print("⚠️  No Etherscan API key found in .env")
        print("   Using 'demo' key (may be rate limited)")
    else:
        print(f"✅ Etherscan API key loaded: {etherscan_key[:10]}...")
    
    # Initialize with low threshold for testing
    whale_tracker = WhaleTracker(
        btc_threshold_usd=50_000,
        eth_threshold_usd=25_000,  # $25K for testing
        api_keys={'etherscan': etherscan_key}
    )
    
    eth_monitor = EthereumWhaleMonitor(whale_tracker)
    
    print(f"✅ ETH monitor initialized")
    print(f"   Threshold: ${whale_tracker.eth_threshold:,}")
    
    async with aiohttp.ClientSession() as session:
        # Get ETH price
        eth_price = await eth_monitor.get_eth_price(session)
        print(f"\n💰 Current ETH Price: ${eth_price:,.2f}")
        
        eth_threshold_amount = whale_tracker.eth_threshold / eth_price
        print(f"🐋 Whale threshold: {eth_threshold_amount:.2f} ETH")
        
        # Fetch large ETH transfers
        print(f"\n🔍 Fetching large ETH transfers from Etherscan...")
        eth_transfers = await eth_monitor.fetch_large_eth_transfers(session)
        
        if eth_transfers:
            print(f"✅ Found {len(eth_transfers)} large ETH transfers!")
            
            print(f"\n📊 Sample ETH transactions:")
            for i, tx in enumerate(eth_transfers[:5]):
                print(f"\n   Transaction {i+1}:")
                print(f"   💰 Amount: {tx['eth_amount']:.4f} ETH")
                print(f"   💵 Value: ${tx['usd_value']:,.2f}")
                print(f"   📤 From: {tx['from'][:16]}...")
                print(f"   📥 To: {tx['to'][:16]}...")
                print(f"   🔗 Hash: {tx['hash'][:16]}...")
                print(f"   📦 Block: {tx.get('block_number', 'N/A')}")
        else:
            print("❌ No large ETH transfers found")
            print("   This could mean:")
            print("   1. No large transfers in recent blocks")
            print("   2. Etherscan API key issue")
            print("   3. Rate limiting")
    
    print(f"\n{'='*50}")
    print("✅ ETH monitoring test complete!")

if __name__ == "__main__":
    asyncio.run(test_eth_monitoring())