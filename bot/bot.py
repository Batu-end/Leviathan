import discord
from discord.ext import commands, tasks
import os
import asyncio
import aiohttp
from datetime import datetime
from dotenv import load_dotenv

# Import our whale tracking system
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fetcher.transactions import WhaleTracker, BitcoinWhaleMonitor, EthereumWhaleMonitor, ExchangeMonitor, WhaleAlert

def run_bot():
    load_dotenv()
    TOKEN = os.getenv('DISCORD_BOT_TOKEN')

    # Use commands.Bot instead of Client for slash commands
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix='!', intents=intents)

    # Initialize whale tracking components
    whale_tracker = WhaleTracker(
        btc_threshold_usd=1_000_000,  # $1M for BTC
        eth_threshold_usd=500_000,    # $500K for ETH
        api_keys={'etherscan': os.getenv('ETHERSCAN_API_KEY', 'demo')}
    )
    
    btc_monitor = BitcoinWhaleMonitor(whale_tracker)
    eth_monitor = EthereumWhaleMonitor(whale_tracker)
    exchange_monitor = ExchangeMonitor(whale_tracker)
    alert_system = WhaleAlert(os.getenv('DISCORD_WEBHOOK_URL'))
    
    # Store references on bot object
    bot.whale_tracker = whale_tracker
    bot.btc_monitor = btc_monitor
    bot.eth_monitor = eth_monitor
    bot.exchange_monitor = exchange_monitor
    bot.alert_system = alert_system
    
    def get_transaction_emoji(tx_type: str) -> str:
        """Get emoji for transaction type"""
        emoji_map = {
            'exchange_withdrawal': '🏦➡️💼',
            'exchange_deposit': '💼➡️🏦', 
            'exchange_transfer': '🏦➡️🏦',
            'wallet_transfer': '💼➡️💼',
            'wallet_consolidation': '🔄💼',
            'wallet_distribution': '💼📤',
            'funds_consolidation': '🔄💰',
            'funds_distribution': '💰📤', 
            'privacy_transaction': '🔒💰',
            'large_transfer': '💰➡️',
            'unknown_transfer': '❓➡️'
        }
        return emoji_map.get(tx_type, '💰')

    @bot.event
    async def on_ready():
        print(f'{bot.user} has surfaced.')
        print('🐋 Whale tracking system initialized')
        print(f'   BTC threshold: ${whale_tracker.btc_threshold:,}')
        print(f'   ETH threshold: ${whale_tracker.eth_threshold:,}')
        
        # Start whale monitoring
        if not whale_monitor.is_running():
            whale_monitor.start()
        
        # Sync slash commands
        try:
            synced = await bot.tree.sync()
            print(f'Synced {len(synced)} command(s)')
        except Exception as e:
            print(f'Failed to sync commands: {e}')

    @bot.tree.command(name="whale_check", description="Check for recent whale activity")
    async def whale_check(interaction: discord.Interaction):
        """Manual whale activity check"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🐋 Whale Activity Check",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        
        try:
            async with aiohttp.ClientSession() as session:
                # Get current prices
                btc_price = await btc_monitor.get_btc_price(session)
                eth_price = await eth_monitor.get_eth_price(session)
                
                embed.add_field(
                    name="📊 Current Prices",
                    value=f"**BTC:** ${btc_price:,.2f}\n**ETH:** ${eth_price:,.2f}",
                    inline=True
                )
                
                # Check for recent whale activity
                btc_transactions = await btc_monitor.fetch_large_transactions(session)
                btc_mempool = await btc_monitor.monitor_mempool(session)
                
                # Monitor US exchanges
                coinbase_btc = await exchange_monitor.monitor_coinbase_pro_orderbook(session, 'BTC-USD')
                coinbase_eth = await exchange_monitor.monitor_coinbase_pro_orderbook(session, 'ETH-USD')
                kraken_btc = await exchange_monitor.monitor_kraken_orderbook(session, 'BTCUSD')
                kraken_eth = await exchange_monitor.monitor_kraken_orderbook(session, 'ETHUSD')
                
                # Combine all exchange orders
                btc_orders = coinbase_btc + kraken_btc
                eth_orders = coinbase_eth + kraken_eth
                
                # Format results
                btc_summary = f"**Confirmed:** {len(btc_transactions)}\n**Pending:** {len(btc_mempool)}\n**Exchange:** {len(btc_orders)}"
                eth_summary = f"**Exchange:** {len(eth_orders)}"
                
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
                
                # Show recent large transactions with type analysis
                if btc_transactions:
                    recent_btc = btc_transactions[:3]
                    btc_details = []
                    for tx in recent_btc:
                        tx_type = tx.get('transaction_type', 'transfer')
                        tx_emoji = get_transaction_emoji(tx_type)
                        
                        # Format addresses for display
                        from_info = ""
                        to_info = ""
                        
                        if tx.get('from_addresses'):
                            from_entity = tx['from_addresses'][0].get('entity', 'Unknown')
                            from_info = f" from {from_entity}"
                        
                        if tx.get('to_addresses'):
                            to_entity = tx['to_addresses'][0].get('entity', 'Unknown') 
                            to_info = f" to {to_entity}"
                        
                        btc_details.append(
                            f"{tx_emoji} **{tx['btc_amount']:.2f} BTC** (${tx['usd_value']:,.0f})\n"
                            f"   Type: {tx_type.replace('_', ' ').title()}{from_info}{to_info}"
                        )
                    
                    embed.add_field(
                        name="📈 Recent Large BTC Transactions",
                        value="\n\n".join(btc_details)[:1024],
                        inline=False
                    )
                
                if btc_orders:
                    order_details = "\n".join([
                        f"• **{order['side'].upper()}** {order['quantity']:.2f} BTC @ ${order['price']:,.0f}"
                        for order in btc_orders[:3]
                    ])
                    embed.add_field(
                        name="📊 Large BTC Orders",
                        value=order_details[:1024],
                        inline=False
                    )
                
        except Exception as e:
            embed.add_field(
                name="❌ Error",
                value=f"Failed to fetch whale data: {str(e)[:200]}",
                inline=False
            )
        
        await interaction.followup.send(embed=embed)

    @bot.tree.command(name="whale_config", description="Configure whale tracking thresholds")
    async def whale_config(interaction: discord.Interaction, 
                          btc_threshold: int = None, 
                          eth_threshold: int = None):
        """Configure whale tracking thresholds"""
        embed = discord.Embed(
            title="🐋 Whale Tracker Configuration",
            color=0x0099ff
        )
        
        if btc_threshold is not None:
            whale_tracker.btc_threshold = btc_threshold
            embed.add_field(
                name="₿ BTC Threshold Updated",
                value=f"${btc_threshold:,}",
                inline=True
            )
        
        if eth_threshold is not None:
            whale_tracker.eth_threshold = eth_threshold
            embed.add_field(
                name="⟠ ETH Threshold Updated", 
                value=f"${eth_threshold:,}",
                inline=True
            )
        
        # Show current settings
        embed.add_field(
            name="📊 Current Thresholds",
            value=f"**BTC:** ${whale_tracker.btc_threshold:,}\n**ETH:** ${whale_tracker.eth_threshold:,}",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="whale_stats", description="Show whale tracking statistics")
    async def whale_stats(interaction: discord.Interaction):
        """Show whale tracking stats and system status"""
        embed = discord.Embed(
            title="📊 Whale Tracker Statistics",
            color=0xff9900,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="🎯 Detection Thresholds",
            value=f"**BTC:** ${whale_tracker.btc_threshold:,}\n**ETH:** ${whale_tracker.eth_threshold:,}",
            inline=True
        )
        
        embed.add_field(
            name="🔗 Data Sources",
            value="• Blockchain.info (BTC)\n• Etherscan (ETH)\n• Coinbase Pro (Orders)\n• Kraken (Orders)\n• Gemini (Orders)\n• CoinGecko (Prices)",
            inline=True
        )
        
        status_emoji = "🟢" if whale_monitor.is_running() else "🔴"
        embed.add_field(
            name="⚡ System Status",
            value=f"{status_emoji} {'Online' if whale_monitor.is_running() else 'Offline'}\n🔄 Auto-monitoring",
            inline=True
        )
        
        if hasattr(alert_system, 'seen_transactions'):
            embed.add_field(
                name="📈 Session Stats",
                value=f"**Alerts sent:** {len(alert_system.seen_transactions)}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="whale_prices", description="Get current BTC and ETH prices")
    async def whale_prices(interaction: discord.Interaction):
        """Quick price check"""
        await interaction.response.defer()
        
        try:
            async with aiohttp.ClientSession() as session:
                btc_price = await btc_monitor.get_btc_price(session)
                eth_price = await eth_monitor.get_eth_price(session)
                
                embed = discord.Embed(
                    title="💰 Current Crypto Prices",
                    color=0xffd700,
                    timestamp=datetime.utcnow()
                )
                
                embed.add_field(
                    name="₿ Bitcoin",
                    value=f"**${btc_price:,.2f}**",
                    inline=True
                )
                
                embed.add_field(
                    name="⟠ Ethereum", 
                    value=f"**${eth_price:,.2f}**",
                    inline=True
                )
                
                # Calculate whale thresholds in native currency
                btc_whale_amount = whale_tracker.btc_threshold / btc_price
                eth_whale_amount = whale_tracker.eth_threshold / eth_price
                
                embed.add_field(
                    name="🐋 Whale Thresholds",
                    value=f"**BTC:** {btc_whale_amount:.2f} BTC\n**ETH:** {eth_whale_amount:.2f} ETH",
                    inline=False
                )
                
        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Failed to fetch prices: {str(e)}",
                color=0xff0000
            )
        
        await interaction.followup.send(embed=embed)

    @tasks.loop(minutes=5)
    async def whale_monitor():
        """Background task to monitor for whale activity"""
        try:
            async with aiohttp.ClientSession() as session:
                # Update prices
                await asyncio.gather(
                    btc_monitor.get_btc_price(session),
                    eth_monitor.get_eth_price(session)
                )
                
                # Monitor all sources (US exchanges)
                results = await asyncio.gather(
                    btc_monitor.fetch_large_transactions(session),
                    btc_monitor.monitor_mempool(session),
                    exchange_monitor.monitor_coinbase_pro_orderbook(session, 'BTC-USD'),
                    exchange_monitor.monitor_coinbase_pro_orderbook(session, 'ETH-USD'),
                    exchange_monitor.monitor_kraken_orderbook(session, 'BTCUSD'),
                    exchange_monitor.monitor_kraken_orderbook(session, 'ETHUSD'),
                    exchange_monitor.monitor_gemini_orderbook(session, 'btcusd'),
                    exchange_monitor.monitor_gemini_orderbook(session, 'ethusd'),
                    return_exceptions=True
                )
                
                # Process whale activities
                whale_alerts = []
                for result in results:
                    if isinstance(result, list):
                        whale_alerts.extend(result)
                
                # Send alerts to the first text channel (you can customize this)
                if whale_alerts and bot.guilds:
                    channel = discord.utils.get(bot.guilds[0].channels, type=discord.ChannelType.text)
                    
                    for whale_activity in whale_alerts[:3]:  # Limit to 3 alerts per cycle
                        embed = discord.Embed(
                            title="🚨 WHALE ALERT 🚨",
                            color=0xff0000,
                            timestamp=datetime.utcnow()
                        )
                        
                        if whale_activity['type'] == 'bitcoin_transfer':
                            tx_type = whale_activity.get('transaction_type', 'transfer')
                            tx_emoji = get_transaction_emoji(tx_type)
                            
                            # Build description with transaction details
                            description = f"{tx_emoji} **Large BTC {tx_type.replace('_', ' ').title()} Detected**\n\n"
                            description += f"💰 **Amount:** {whale_activity['btc_amount']:.2f} BTC\n"
                            description += f"💵 **Value:** ${whale_activity['usd_value']:,.2f}\n"
                            
                            # Add from/to information if available
                            if whale_activity.get('from_addresses'):
                                from_entity = whale_activity['from_addresses'][0].get('entity', 'Unknown')
                                description += f"📤 **From:** {from_entity}\n"
                            
                            if whale_activity.get('to_addresses'):
                                to_entity = whale_activity['to_addresses'][0].get('entity', 'Unknown')
                                description += f"📥 **To:** {to_entity}\n"
                            
                            embed.description = description
                            embed.add_field(name="🔗 Hash", value=f"`{whale_activity['hash'][:16]}...`", inline=False)
                            
                            # Add transaction pattern info
                            if whale_activity.get('pattern'):
                                pattern = whale_activity['pattern'].replace('_', ' ').title()
                                embed.add_field(name="📊 Pattern", value=pattern, inline=True)
                            
                        elif whale_activity['type'] == 'exchange_order':
                            emoji = "📈" if whale_activity['side'] == 'buy' else "📉"
                            embed.description = f"{emoji} **Large {whale_activity['side'].title()} Order**\n\n🏛️ **Exchange:** {whale_activity['exchange'].title()}\n💱 **Symbol:** {whale_activity['symbol']}\n💰 **Value:** ${whale_activity['usd_value']:,.2f}"
                        
                        if channel:
                            await channel.send(embed=embed)
                
        except Exception as e:
            print(f"Whale monitoring error: {e}")

    @whale_monitor.before_loop
    async def before_whale_monitor():
        """Wait for bot to be ready before starting monitoring"""
        await bot.wait_until_ready()

    # Traditional command for backwards compatibility
    @bot.command(name='whales')
    async def whales_command(ctx):
        """Legacy command - use /whale_check instead"""
        await ctx.send("🐋 Use `/whale_check` for the interactive whale activity report!")

    bot.run(TOKEN)