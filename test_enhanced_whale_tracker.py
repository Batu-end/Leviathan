#!/usr/bin/env python3
"""
Enhanced test to demonstrate transaction type classification
"""

import asyncio
import sys
import os
import aiohttp

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetcher.transactions import WhaleTracker, BitcoinWhaleMonitor

async def test_transaction_classification():
    """Test transaction type classification with detailed output"""
    
    print("🐋 Testing Enhanced Whale Tracker with Transaction Classification")
    print("=" * 70)
    
    # Initialize with lower thresholds for testing
    whale_tracker = WhaleTracker(
        btc_threshold_usd=50_000,    # $50K for testing
        eth_threshold_usd=25_000,    # $25K for testing
    )
    
    btc_monitor = BitcoinWhaleMonitor(whale_tracker)
    
    print("✓ Enhanced whale tracker initialized with transaction classification")
    
    async with aiohttp.ClientSession() as session:
        # Get current price
        btc_price = await btc_monitor.get_btc_price(session)
        print(f"✓ BTC Price: ${btc_price:,.2f}")
        
        print("\n🔍 Fetching and analyzing Bitcoin transactions...")
        btc_transactions = await btc_monitor.fetch_large_transactions(session)
        
        print(f"✓ Found {len(btc_transactions)} large BTC transactions with classification")
        
        # Show detailed analysis of first few transactions
        for i, tx in enumerate(btc_transactions[:5]):
            print(f"\n📊 Transaction {i+1}:")
            print(f"   💰 Amount: {tx['btc_amount']:.4f} BTC (${tx['usd_value']:,.2f})")
            print(f"   🏷️  Type: {tx.get('transaction_type', 'unknown').replace('_', ' ').title()}")
            print(f"   📈 Pattern: {tx.get('pattern', 'unknown').replace('_', ' ').title()}")
            print(f"   🔗 Hash: {tx['hash'][:16]}...")
            
            # Show from addresses
            if tx.get('from_addresses'):
                print("   📤 From:")
                for addr in tx['from_addresses'][:2]:
                    entity = addr.get('entity', 'Unknown')[:30]  # Truncate long names
                    addr_type = addr.get('type', 'unknown')
                    print(f"      • {entity} ({addr_type})")
            
            # Show to addresses  
            if tx.get('to_addresses'):
                print("   📥 To:")
                for addr in tx['to_addresses'][:2]:
                    entity = addr.get('entity', 'Unknown')[:30]
                    addr_type = addr.get('type', 'unknown') 
                    value = addr.get('value', 0)
                    print(f"      • {entity} ({addr_type}) - {value:.4f} BTC")
            
            print(f"   📊 I/O: {tx.get('total_inputs', '?')} inputs → {tx.get('total_outputs', '?')} outputs")
        
        print(f"\n🔍 Testing mempool analysis...")
        mempool_txs = await btc_monitor.monitor_mempool(session)
        print(f"✓ Found {len(mempool_txs)} large pending transactions")
        
        if mempool_txs:
            print(f"\n📊 Sample pending transaction:")
            tx = mempool_txs[0]
            print(f"   💰 Amount: {tx['btc_amount']:.4f} BTC (${tx['usd_value']:,.2f})")
            print(f"   🏷️  Type: {tx.get('transaction_type', 'unknown').replace('_', ' ').title()}")
            print(f"   ⏳ Status: Pending confirmation")
    
    print(f"\n✅ Enhanced whale tracker test completed!")
    print(f"The system can now classify transactions as:")
    print(f"   🏦 Exchange withdrawals/deposits")
    print(f"   💼 Wallet transfers") 
    print(f"   🔄 Fund consolidations")
    print(f"   📤 Fund distributions")
    print(f"   🔒 Privacy transactions")
    print(f"   And more transaction patterns!")

if __name__ == "__main__":
    asyncio.run(test_transaction_classification())