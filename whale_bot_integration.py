"""
Discord Bot Integration for Whale Tracker

Add these commands to your existing Discord bot to provide whale tracking functionality.
"""

import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
from datetime import datetime
from fetcher.transactions import WhaleTracker, BitcoinWhaleMonitor, EthereumWhaleMonitor, ExchangeMonitor, WhaleAlert

class WhaleCog(commands.Cog):
    """Discord bot commands for whale tracking"""
    
    def __init__(self, bot):
        self.bot = bot
        self.whale_tracker = None
        self.setup_whale_tracker()
        self.whale_monitor_task.start()  # Start background monitoring
        
    def setup_whale_tracker(self):
        """Initialize the whale tracking components"""
        api_keys = {
            'etherscan': 'demo',  # Replace with actual key
        }
        
        self.whale_tracker = WhaleTracker(
            btc_threshold_usd=1_000_000,
            eth_threshold_usd=500_000,
            api_keys=api_keys
        )
        
        self.btc_monitor = BitcoinWhaleMonitor(self.whale_tracker)
        self.eth_monitor = EthereumWhaleMonitor(self.whale_tracker)
        self.exchange_monitor = ExchangeMonitor(self.whale_tracker)
        self.alert_system = WhaleAlert()

    @commands.slash_command(name="whale_check", description="Check for recent whale activity")
    async def whale_check(self, ctx):
        """Manual whale activity check"""
        await ctx.defer()  # Let Discord know we're processing
        
        embed = discord.Embed(
            title="🐋 Whale Activity Check",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get current prices
                btc_price = await self.btc_monitor.get_btc_price(session)
                eth_price = await self.eth_monitor.get_eth_price(session)
                
                embed.add_field(
                    name="📊 Current Prices",
                    value=f"BTC: ${btc_price:,.2f}\nETH: ${eth_price:,.2f}",
                    inline=True
                )
                
                # Check for recent whale activity
                btc_transactions = await self.btc_monitor.fetch_large_transactions(session)
                btc_mempool = await self.btc_monitor.monitor_mempool(session)
                btc_orders = await self.exchange_monitor.monitor_binance_orderbook(session, 'BTCUSDT')
                eth_orders = await self.exchange_monitor.monitor_binance_orderbook(session, 'ETHUSDT')
                
                # Format results
                btc_summary = f"Confirmed: {len(btc_transactions)}\nPending: {len(btc_mempool)}\nExchange Orders: {len(btc_orders)}"
                eth_summary = f"Exchange Orders: {len(eth_orders)}"
                
                embed.add_field(
                    name="₿ Bitcoin Activity",
                    value=btc_summary,
                    inline=True
                )
                
                embed.add_field(
                    name="⟠ Ethereum Activity", 
                    value=eth_summary,
                    inline=True
                )
                
                # Show recent large transactions
                if btc_transactions:
                    recent_btc = btc_transactions[:3]
                    btc_details = "\n".join([
                        f"• {tx['btc_amount']:.2f} BTC (${tx['usd_value']:,.0f})"
                        for tx in recent_btc
                    ])
                    embed.add_field(
                        name="📈 Recent Large BTC Transactions",
                        value=btc_details[:1024],  # Discord field limit
                        inline=False
                    )
                
        except Exception as e:
            embed.add_field(
                name="❌ Error",
                value=f"Failed to fetch whale data: {str(e)[:200]}",
                inline=False
            )
        
        await ctx.followup.send(embed=embed)

    @commands.slash_command(name="whale_config", description="Configure whale tracking thresholds")
    async def whale_config(self, ctx, 
                          btc_threshold: int = None, 
                          eth_threshold: int = None):
        """Configure whale tracking thresholds"""
        embed = discord.Embed(
            title="🐋 Whale Tracker Configuration",
            color=0x0099ff
        )
        
        if btc_threshold is not None:
            self.whale_tracker.btc_threshold = btc_threshold
            embed.add_field(
                name="₿ BTC Threshold Updated",
                value=f"${btc_threshold:,}",
                inline=True
            )
        
        if eth_threshold is not None:
            self.whale_tracker.eth_threshold = eth_threshold
            embed.add_field(
                name="⟠ ETH Threshold Updated", 
                value=f"${eth_threshold:,}",
                inline=True
            )
        
        # Show current settings
        embed.add_field(
            name="📊 Current Thresholds",
            value=f"BTC: ${self.whale_tracker.btc_threshold:,}\nETH: ${self.whale_tracker.eth_threshold:,}",
            inline=False
        )
        
        await ctx.respond(embed=embed)

    @commands.slash_command(name="whale_stats", description="Show whale tracking statistics")
    async def whale_stats(self, ctx):
        """Show whale tracking stats and system status"""
        embed = discord.Embed(
            title="📊 Whale Tracker Statistics",
            color=0xff9900,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🎯 Detection Thresholds",
            value=f"BTC: ${self.whale_tracker.btc_threshold:,}\nETH: ${self.whale_tracker.eth_threshold:,}",
            inline=True
        )
        
        embed.add_field(
            name="🔗 Data Sources",
            value="• Blockchain.info (BTC)\n• Etherscan (ETH)\n• Binance (Orders)\n• CoinGecko (Prices)",
            inline=True
        )
        
        embed.add_field(
            name="⚡ System Status",
            value="🟢 Online\n🔄 Auto-monitoring",
            inline=True
        )
        
        if hasattr(self.alert_system, 'seen_transactions'):
            embed.add_field(
                name="📈 Session Stats",
                value=f"Alerts sent: {len(self.alert_system.seen_transactions)}",
                inline=False
            )
        
        await ctx.respond(embed=embed)

    @tasks.loop(minutes=5)
    async def whale_monitor_task(self):
        """Background task to monitor for whale activity"""
        try:
            async with aiohttp.ClientSession() as session:
                # Update prices
                await asyncio.gather(
                    self.btc_monitor.get_btc_price(session),
                    self.eth_monitor.get_eth_price(session)
                )
                
                # Monitor all sources
                results = await asyncio.gather(
                    self.btc_monitor.fetch_large_transactions(session),
                    self.btc_monitor.monitor_mempool(session),
                    self.exchange_monitor.monitor_binance_orderbook(session, 'BTCUSDT'),
                    self.exchange_monitor.monitor_binance_orderbook(session, 'ETHUSDT'),
                    return_exceptions=True
                )
                
                # Check for new whale activities and send to default channel
                for result in results:
                    if isinstance(result, list):
                        for whale_activity in result:
                            # Create Discord alert
                            embed = discord.Embed(
                                title="🐋 WHALE ALERT",
                                description=self.alert_system.format_alert_message(whale_activity),
                                color=0xff0000,
                                timestamp=datetime.utcnow()
                            )
                            
                            # Send to a designated whale alerts channel
                            # Replace with your actual channel ID
                            channel = self.bot.get_channel(1234567890)  # Your channel ID
                            if channel:
                                await channel.send(embed=embed)
                                
        except Exception as e:
            print(f"Whale monitoring error: {e}")

    @whale_monitor_task.before_loop
    async def before_whale_monitor_task(self):
        """Wait for bot to be ready before starting monitoring"""
        await self.bot.wait_until_ready()

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.whale_monitor_task.cancel()


def setup(bot):
    """Setup function to add the cog to the bot"""
    bot.add_cog(WhaleCog(bot))


# Alternative: Add directly to your existing bot.py
async def add_whale_commands(client):
    """
    Add whale tracking commands to your existing Discord client
    Call this function in your bot.py setup
    """
    
    # Initialize whale tracker
    whale_tracker = WhaleTracker(
        btc_threshold_usd=1_000_000,
        eth_threshold_usd=500_000,
        api_keys={'etherscan': 'demo'}
    )
    
    btc_monitor = BitcoinWhaleMonitor(whale_tracker)
    eth_monitor = EthereumWhaleMonitor(whale_tracker)
    exchange_monitor = ExchangeMonitor(whale_tracker)
    
    @client.slash_command(name="whales", description="Check recent whale activity")
    async def check_whales(ctx):
        await ctx.defer()
        
        async with aiohttp.ClientSession() as session:
            btc_price = await btc_monitor.get_btc_price(session)
            btc_transactions = await btc_monitor.fetch_large_transactions(session)
            
            embed = discord.Embed(
                title="🐋 Whale Activity",
                description=f"BTC Price: ${btc_price:,.2f}\nLarge transactions: {len(btc_transactions)}",
                color=0x00ff00
            )
            
        await ctx.followup.send(embed=embed)