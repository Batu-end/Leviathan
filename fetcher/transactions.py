"""
Bitcoin and Ethereum Whale Transaction Tracker

This module provides functionality to track large cryptocurrency transactions
that could indicate whale activity across multiple data sources.

Features:
- Monitor large BTC/ETH on-chain transactions
- Track DEX swaps above threshold amounts
- Monitor exchange order book for large orders
- Real-time alerts via Discord integration
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import aiohttp
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WhaleTracker:
    """Main class for tracking whale movements across BTC and ETH"""
    
    def __init__(self, 
                 btc_threshold_usd: float = 1_000_000,  # $1M+ transactions
                 eth_threshold_usd: float = 500_000,    # $500K+ transactions
                 api_keys: Optional[Dict[str, str]] = None):
        """
        Initialize whale tracker
        
        Args:
            btc_threshold_usd: Minimum USD value to consider whale activity for BTC
            eth_threshold_usd: Minimum USD value to consider whale activity for ETH
            api_keys: Dictionary of API keys for various services
        """
        self.btc_threshold = btc_threshold_usd
        self.eth_threshold = eth_threshold_usd
        self.api_keys = api_keys or {}
        
        # Rate limiting
        self.last_requests = {}
        self.request_delays = {
            'etherscan': 0.2,        # 5 requests per second
            'blockchain_info': 0.1,   # 10 requests per second
            'coinbase_pro': 0.1,     # 10 requests per second
            'kraken': 0.2,           # 5 requests per second
            'gemini': 0.1            # 10 requests per second
        }
        
        # Known exchange addresses (US-focused exchanges)
        self.known_addresses = {
            'exchanges': {
                # Coinbase (US-based)
                'bc1qgdjqv0av3q56jvd82tkdjpy7gdp9ut8tlqmgrpmv24sq90ecnvqqjwvw97': 'Coinbase',
                '3M219KBk7ZjsPUe7UpzPcTg1z5y7R25Acz': 'Coinbase',
                'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq': 'Coinbase',
                '3FupZp77ySr7jwoLYBUagcEp3nhKxggdy5': 'Coinbase',
                # Kraken (US-accessible)
                'bc1qjasf9z3h7w3jspkhtgatgpyvvzgpa2wwd2lr0eh5tx44reyn2k7sfc27a4': 'Kraken',
                '3BMEXhash77KHeEqgQkZTBC5m4D7dTwq6J': 'Kraken',
                'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh': 'Kraken',
                # Gemini (US-based)
                'bc1qmxjefnuy06v345v6vhwpwt05dztztmx2xajzd6xtzch7cceh6k8q7xl5ah': 'Gemini',
                '3DZ1K9a8rQn3qNLNLHbfkKBtkGWbMw6xhF': 'Gemini',
                # Binance (marked for reference but restricted in US)
                'bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h': 'Binance (Non-US)',
                '34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo': 'Binance (Non-US)',
                # Add more US exchange addresses as needed
            },
            'mixing_services': {
                # Known mixers/tumblers
                '1mixer': 'Mixing Service',
                # Add more mixing service patterns
            }
        }
        
    async def rate_limit(self, service: str):
        """Simple rate limiting"""
        if service in self.last_requests:
            elapsed = asyncio.get_event_loop().time() - self.last_requests[service]
            delay = self.request_delays.get(service, 1.0)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        self.last_requests[service] = asyncio.get_event_loop().time()
    
    def classify_address(self, address: str) -> Tuple[str, str]:
        """
        Classify Bitcoin address type and entity
        Returns: (address_type, entity_name)
        """
        if not address:
            return 'unknown', 'Unknown'
            
        # Check known exchanges
        if address in self.known_addresses['exchanges']:
            return 'exchange', self.known_addresses['exchanges'][address]
            
        # Check mixing services
        for pattern, name in self.known_addresses['mixing_services'].items():
            if pattern in address.lower():
                return 'mixer', name
        
        # Analyze address patterns
        if address.startswith('bc1q'):
            if len(address) > 50:
                return 'wallet', 'Cold Storage (Bech32)'
            else:
                return 'wallet', 'Personal Wallet (Bech32)'
        elif address.startswith('3'):
            return 'wallet', 'Multi-sig Wallet'
        elif address.startswith('1'):
            return 'wallet', 'Legacy Wallet'
        else:
            return 'unknown', 'Unknown Address Type'
    
    def analyze_transaction_pattern(self, tx_data: Dict) -> str:
        """
        Analyze transaction pattern to determine likely transaction type
        """
        inputs = tx_data.get('inputs', [])
        outputs = tx_data.get('out', [])
        
        if not inputs or not outputs:
            return 'unknown'
        
        # Count unique addresses
        input_addresses = set()
        output_addresses = set()
        
        for inp in inputs:
            if 'prev_out' in inp and 'addr' in inp['prev_out']:
                input_addresses.add(inp['prev_out']['addr'])
        
        for out in outputs:
            if 'addr' in out:
                output_addresses.add(out['addr'])
        
        # Classification logic
        if len(input_addresses) == 1 and len(output_addresses) == 1:
            return 'simple_transfer'
        elif len(input_addresses) == 1 and len(output_addresses) == 2:
            # Likely transfer with change
            return 'wallet_transfer'
        elif len(input_addresses) > 5 and len(output_addresses) == 1:
            return 'consolidation'
        elif len(input_addresses) == 1 and len(output_addresses) > 10:
            return 'distribution'
        elif len(input_addresses) > 1 and len(output_addresses) > 1:
            return 'complex_transaction'
        else:
            return 'standard_transaction'


class BitcoinWhaleMonitor:
    """Monitor Bitcoin whale transactions"""
    
    def __init__(self, whale_tracker: WhaleTracker):
        self.tracker = whale_tracker
        self.btc_price = 0.0
    
    def _determine_transaction_type(self, from_addresses: List[Dict], to_addresses: List[Dict], pattern: str) -> str:
        """Determine the most likely transaction type based on address analysis"""
        if not from_addresses or not to_addresses:
            return 'unknown_transfer'
        
        from_types = [addr['type'] for addr in from_addresses]
        to_types = [addr['type'] for addr in to_addresses]
        
        # Exchange to wallet
        if 'exchange' in from_types and 'wallet' in to_types:
            return 'exchange_withdrawal'
        
        # Wallet to exchange  
        if 'wallet' in from_types and 'exchange' in to_types:
            return 'exchange_deposit'
        
        # Exchange to exchange
        if 'exchange' in from_types and 'exchange' in to_types:
            return 'exchange_transfer'
        
        # Wallet to wallet
        if all(t == 'wallet' for t in from_types + to_types):
            if pattern == 'consolidation':
                return 'wallet_consolidation'
            elif pattern == 'distribution':
                return 'wallet_distribution'
            else:
                return 'wallet_transfer'
        
        # Mixing service involved
        if 'mixer' in from_types or 'mixer' in to_types:
            return 'privacy_transaction'
        
        # Default based on pattern
        if pattern == 'consolidation':
            return 'funds_consolidation'
        elif pattern == 'distribution':
            return 'funds_distribution'
        else:
            return 'large_transfer'
        
    async def get_btc_price(self, session: aiohttp.ClientSession) -> float:
        """Get current BTC price from CoinGecko"""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
            async with session.get(url) as response:
                data = await response.json()
                self.btc_price = data['bitcoin']['usd']
                return self.btc_price
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to get BTC price: %s", e)
            return self.btc_price or 45000  # Fallback price
    
    async def fetch_large_transactions(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Fetch large Bitcoin transactions from multiple sources"""
        await self.tracker.rate_limit('blockchain_info')
        
        try:
            # Get latest blocks and scan for large transactions
            url = "https://blockchain.info/latestblock"
            async with session.get(url) as response:
                latest_block = await response.json()
                
            # Get block details
            block_hash = latest_block['hash']
            block_url = f"https://blockchain.info/rawblock/{block_hash}"
            
            await self.tracker.rate_limit('blockchain_info')
            async with session.get(block_url) as response:
                block_data = await response.json()
                
            large_txs = []
            for tx in block_data.get('tx', []):
                # Calculate transaction value
                total_output = sum(output.get('value', 0) for output in tx.get('out', []))
                btc_amount = total_output / 100000000  # Convert satoshi to BTC
                usd_value = btc_amount * self.btc_price
                
                if usd_value >= self.tracker.btc_threshold:
                    # Analyze transaction pattern
                    tx_pattern = self.tracker.analyze_transaction_pattern(tx)
                    
                    # Classify addresses
                    from_addresses = []
                    to_addresses = []
                    
                    # Get input addresses
                    for inp in tx.get('inputs', []):
                        if 'prev_out' in inp and 'addr' in inp['prev_out']:
                            addr = inp['prev_out']['addr']
                            addr_type, entity = self.tracker.classify_address(addr)
                            from_addresses.append({
                                'address': addr,
                                'type': addr_type,
                                'entity': entity
                            })
                    
                    # Get output addresses
                    for out in tx.get('out', []):
                        if 'addr' in out:
                            addr = out['addr']
                            addr_type, entity = self.tracker.classify_address(addr)
                            to_addresses.append({
                                'address': addr,
                                'type': addr_type,
                                'entity': entity,
                                'value': out.get('value', 0) / 100000000  # BTC amount
                            })
                    
                    # Determine transaction type based on addresses
                    transaction_type = self._determine_transaction_type(from_addresses, to_addresses, tx_pattern)
                    
                    large_txs.append({
                        'hash': tx['hash'],
                        'btc_amount': btc_amount,
                        'usd_value': usd_value,
                        'timestamp': tx.get('time', 0),
                        'block_height': latest_block['height'],
                        'type': 'bitcoin_transfer',
                        'transaction_type': transaction_type,
                        'pattern': tx_pattern,
                        'from_addresses': from_addresses[:3],  # Limit for display
                        'to_addresses': to_addresses[:3],      # Limit for display
                        'total_inputs': len(tx.get('inputs', [])),
                        'total_outputs': len(tx.get('out', []))
                    })
                    
            return large_txs
            
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to fetch BTC transactions: %s", e)
            return []
    
    async def monitor_mempool(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Monitor Bitcoin mempool for large pending transactions"""
        try:
            await self.tracker.rate_limit('blockchain_info')
            url = "https://blockchain.info/unconfirmed-transactions?format=json"
            
            async with session.get(url) as response:
                data = await response.json()
                
            large_pending = []
            for tx in data.get('txs', [])[:50]:  # Check first 50 transactions
                total_output = sum(output.get('value', 0) for output in tx.get('out', []))
                btc_amount = total_output / 100000000
                usd_value = btc_amount * self.btc_price
                
                if usd_value >= self.tracker.btc_threshold:
                    # Analyze transaction pattern for mempool transactions too
                    tx_pattern = self.tracker.analyze_transaction_pattern(tx)
                    
                    # Classify addresses
                    from_addresses = []
                    to_addresses = []
                    
                    # Get input addresses
                    for inp in tx.get('inputs', []):
                        if 'prev_out' in inp and 'addr' in inp['prev_out']:
                            addr = inp['prev_out']['addr']
                            addr_type, entity = self.tracker.classify_address(addr)
                            from_addresses.append({
                                'address': addr,
                                'type': addr_type,
                                'entity': entity
                            })
                    
                    # Get output addresses  
                    for out in tx.get('out', []):
                        if 'addr' in out:
                            addr = out['addr']
                            addr_type, entity = self.tracker.classify_address(addr)
                            to_addresses.append({
                                'address': addr,
                                'type': addr_type,
                                'entity': entity,
                                'value': out.get('value', 0) / 100000000
                            })
                    
                    transaction_type = self._determine_transaction_type(from_addresses, to_addresses, tx_pattern)
                    
                    large_pending.append({
                        'hash': tx['hash'],
                        'btc_amount': btc_amount,
                        'usd_value': usd_value,
                        'timestamp': tx.get('time', 0),
                        'status': 'pending',
                        'type': 'bitcoin_pending',
                        'transaction_type': transaction_type,
                        'pattern': tx_pattern,
                        'from_addresses': from_addresses[:3],
                        'to_addresses': to_addresses[:3]
                    })
                    
            return large_pending
            
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to monitor BTC mempool: %s", e)
            return []


class EthereumWhaleMonitor:
    """Monitor Ethereum whale transactions and DEX activity"""
    
    def __init__(self, whale_tracker: WhaleTracker):
        self.tracker = whale_tracker
        self.eth_price = 0.0
        
    async def get_eth_price(self, session: aiohttp.ClientSession) -> float:
        """Get current ETH price"""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"
            async with session.get(url) as response:
                data = await response.json()
                self.eth_price = data['ethereum']['usd']
                return self.eth_price
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to get ETH price: %s", e)
            return self.eth_price or 2500  # Fallback price
    
    async def fetch_large_eth_transfers(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Fetch large ETH transfers using Etherscan API"""
        if 'etherscan' not in self.tracker.api_keys:
            logger.warning("Etherscan API key not provided")
            return []
            
        try:
            await self.tracker.rate_limit('etherscan')
            
            # Get latest block number
            url = f"https://api.etherscan.io/api?module=proxy&action=eth_blockNumber&apikey={self.tracker.api_keys['etherscan']}"
            async with session.get(url) as response:
                data = await response.json()
                latest_block = int(data['result'], 16)
            
            # Get transactions from recent blocks
            large_transfers = []
            for block_offset in range(5):  # Check last 5 blocks
                block_num = latest_block - block_offset
                
                await self.tracker.rate_limit('etherscan')
                block_url = f"https://api.etherscan.io/api?module=proxy&action=eth_getBlockByNumber&tag=0x{block_num:x}&boolean=true&apikey={self.tracker.api_keys['etherscan']}"
                
                async with session.get(block_url) as response:
                    block_data = await response.json()
                    
                for tx in block_data.get('result', {}).get('transactions', []):
                    if tx.get('value') and tx['value'] != '0x0':
                        wei_amount = int(tx['value'], 16)
                        eth_amount = wei_amount / 10**18
                        usd_value = eth_amount * self.eth_price
                        
                        if usd_value >= self.tracker.eth_threshold:
                            large_transfers.append({
                                'hash': tx['hash'],
                                'eth_amount': eth_amount,
                                'usd_value': usd_value,
                                'from': tx['from'],
                                'to': tx['to'],
                                'block_number': block_num,
                                'type': 'ethereum_transfer'
                            })
                            
            return large_transfers
            
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to fetch ETH transfers: %s", e)
            return []
    
    async def monitor_uniswap_swaps(self, session: aiohttp.ClientSession) -> List[Dict]:
        """Monitor large Uniswap swaps (requires The Graph API or similar)"""
        # This would require a more complex GraphQL implementation
        # For now, return empty list as placeholder
        # session parameter kept for future implementation
        del session  # Acknowledge unused parameter
        logger.info("Uniswap monitoring not implemented yet")
        return []


class ExchangeMonitor:
    """Monitor centralized exchanges for large orders (US-compatible)"""
    
    def __init__(self, whale_tracker: WhaleTracker):
        self.tracker = whale_tracker
    
    async def monitor_coinbase_pro_orderbook(self, session: aiohttp.ClientSession, 
                                           symbol: str = 'BTC-USD') -> List[Dict]:
        """Monitor Coinbase Pro order book for large orders"""
        try:
            await self.tracker.rate_limit('coinbase_pro')
            url = f"https://api.exchange.coinbase.com/products/{symbol}/book?level=2"
            
            async with session.get(url) as response:
                data = await response.json()
                
            large_orders = []
            
            # Check bids (buy orders)
            for price, quantity, _ in data.get('bids', []):
                usd_value = float(price) * float(quantity)
                threshold = self.tracker.btc_threshold if 'BTC' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'coinbase_pro',
                        'symbol': symbol,
                        'side': 'buy',
                        'price': float(price),
                        'quantity': float(quantity),
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
            
            # Check asks (sell orders)
            for price, quantity, _ in data.get('asks', []):
                usd_value = float(price) * float(quantity)
                threshold = self.tracker.btc_threshold if 'BTC' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'coinbase_pro',
                        'symbol': symbol,
                        'side': 'sell',
                        'price': float(price),
                        'quantity': float(quantity),
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
                    
            return large_orders
            
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to monitor Coinbase Pro orderbook: %s", e)
            return []
    
    async def monitor_kraken_orderbook(self, session: aiohttp.ClientSession, 
                                     symbol: str = 'BTCUSD') -> List[Dict]:
        """Monitor Kraken order book for large orders"""
        try:
            await self.tracker.rate_limit('kraken')
            url = f"https://api.kraken.com/0/public/Depth?pair={symbol}&count=100"
            
            async with session.get(url) as response:
                data = await response.json()
                
            if 'error' in data and data['error']:
                logger.error("Kraken API error: %s", data['error'])
                return []
                
            result = data.get('result', {})
            pair_data = list(result.values())[0] if result else {}
            
            large_orders = []
            
            # Check bids (buy orders)
            for price, quantity, _ in pair_data.get('bids', []):
                usd_value = float(price) * float(quantity)
                threshold = self.tracker.btc_threshold if 'BTC' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'kraken',
                        'symbol': symbol,
                        'side': 'buy',
                        'price': float(price),
                        'quantity': float(quantity),
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
            
            # Check asks (sell orders)
            for price, quantity, _ in pair_data.get('asks', []):
                usd_value = float(price) * float(quantity)
                threshold = self.tracker.btc_threshold if 'BTC' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'kraken',
                        'symbol': symbol,
                        'side': 'sell',
                        'price': float(price),
                        'quantity': float(quantity),
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
                    
            return large_orders
            
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to monitor Kraken orderbook: %s", e)
            return []
        
    async def monitor_gemini_orderbook(self, session: aiohttp.ClientSession, 
                                     symbol: str = 'btcusd') -> List[Dict]:
        """Monitor Gemini order book for large orders"""
        try:
            await self.tracker.rate_limit('gemini')
            url = f"https://api.gemini.com/v1/book/{symbol}"
            
            async with session.get(url) as response:
                data = await response.json()
                
            large_orders = []
            
            # Check bids (buy orders)
            for order in data.get('bids', []):
                price = float(order['price'])
                quantity = float(order['amount'])
                usd_value = price * quantity
                threshold = self.tracker.btc_threshold if 'btc' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'gemini',
                        'symbol': symbol.upper(),
                        'side': 'buy',
                        'price': price,
                        'quantity': quantity,
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
            
            # Check asks (sell orders)
            for order in data.get('asks', []):
                price = float(order['price'])
                quantity = float(order['amount'])
                usd_value = price * quantity
                threshold = self.tracker.btc_threshold if 'btc' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'gemini',
                        'symbol': symbol.upper(),
                        'side': 'sell',
                        'price': price,
                        'quantity': quantity,
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
                    
            return large_orders
            
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to monitor Gemini orderbook: %s", e)
            return []
        
    # Keep the old Binance method for backwards compatibility but mark it
    async def monitor_binance_orderbook(self, session: aiohttp.ClientSession, 
                                      symbol: str = 'BTCUSDT') -> List[Dict]:
        """Monitor Binance order book for large orders"""
        try:
            await self.tracker.rate_limit('binance')
            url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=100"
            
            async with session.get(url) as response:
                data = await response.json()
                
            large_orders = []
            
            # Check bids (buy orders)
            for price, quantity in data.get('bids', []):
                usd_value = float(price) * float(quantity)
                threshold = self.tracker.btc_threshold if 'BTC' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'binance',
                        'symbol': symbol,
                        'side': 'buy',
                        'price': float(price),
                        'quantity': float(quantity),
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
            
            # Check asks (sell orders)
            for price, quantity in data.get('asks', []):
                usd_value = float(price) * float(quantity)
                threshold = self.tracker.btc_threshold if 'BTC' in symbol else self.tracker.eth_threshold
                
                if usd_value >= threshold:
                    large_orders.append({
                        'exchange': 'binance',
                        'symbol': symbol,
                        'side': 'sell',
                        'price': float(price),
                        'quantity': float(quantity),
                        'usd_value': usd_value,
                        'type': 'exchange_order'
                    })
                    
            return large_orders
            
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to monitor Binance orderbook: %s", e)
            return []


class WhaleAlert:
    """Handle whale activity alerts and notifications"""
    
    def __init__(self, discord_webhook_url: Optional[str] = None):
        self.webhook_url = discord_webhook_url
        self.seen_transactions = set()  # Prevent duplicate alerts
        
    def format_alert_message(self, whale_data: Dict) -> str:
        """Format whale activity into Discord message"""
        if whale_data['type'] == 'bitcoin_transfer':
            return (f"🐋 **Bitcoin Whale Alert** 🐋\n"
                   f"💰 **Amount:** {whale_data['btc_amount']:.2f} BTC (${whale_data['usd_value']:,.2f})\n"
                   f"📋 **Hash:** `{whale_data['hash'][:16]}...`\n"
                   f"⏰ **Time:** {datetime.fromtimestamp(whale_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
                   
        elif whale_data['type'] == 'ethereum_transfer':
            return (f"🐋 **Ethereum Whale Alert** 🐋\n"
                   f"💰 **Amount:** {whale_data['eth_amount']:.2f} ETH (${whale_data['usd_value']:,.2f})\n"
                   f"📋 **Hash:** `{whale_data['hash'][:16]}...`\n"
                   f"👤 **From:** `{whale_data['from'][:10]}...`\n"
                   f"👤 **To:** `{whale_data['to'][:10]}...`")
                   
        elif whale_data['type'] == 'exchange_order':
            emoji = "📈" if whale_data['side'] == 'buy' else "📉"
            return (f"{emoji} **Large {whale_data['side'].title()} Order** {emoji}\n"
                   f"🏛️ **Exchange:** {whale_data['exchange'].title()}\n"
                   f"💱 **Symbol:** {whale_data['symbol']}\n"
                   f"💰 **Value:** ${whale_data['usd_value']:,.2f}\n"
                   f"💵 **Price:** ${whale_data['price']:,.2f}")
        
        return f"🐋 Whale activity detected: ${whale_data.get('usd_value', 0):,.2f}"
    
    async def send_alert(self, session: aiohttp.ClientSession, whale_data: Dict):
        """Send whale alert to Discord"""
        if not self.webhook_url:
            logger.info("No webhook configured. Alert: %s", self.format_alert_message(whale_data))
            return
            
        # Prevent duplicate alerts
        alert_id = f"{whale_data.get('hash', '')}{whale_data.get('symbol', '')}{whale_data.get('usd_value', 0)}"
        if alert_id in self.seen_transactions:
            return
        self.seen_transactions.add(alert_id)
        
        try:
            message = self.format_alert_message(whale_data)
            payload = {"content": message}
            
            async with session.post(self.webhook_url, json=payload) as response:
                if response.status == 204:
                    logger.info("Alert sent successfully for %s", whale_data['type'])
                else:
                    logger.error("Failed to send alert: %s", response.status)
                    
        except (aiohttp.ClientError, KeyError, ValueError) as e:
            logger.error("Failed to send Discord alert: %s", e)


async def main():
    """Main whale tracking loop"""
    # Initialize components
    api_keys = {
        'etherscan': 'YOUR_ETHERSCAN_API_KEY',  # Get free key from etherscan.io
        # Add other API keys as needed
    }
    
    whale_tracker = WhaleTracker(
        btc_threshold_usd=1_000_000,  # $1M for BTC
        eth_threshold_usd=500_000,    # $500K for ETH
        api_keys=api_keys
    )
    
    btc_monitor = BitcoinWhaleMonitor(whale_tracker)
    eth_monitor = EthereumWhaleMonitor(whale_tracker)
    exchange_monitor = ExchangeMonitor(whale_tracker)
    alert_system = WhaleAlert()  # Add Discord webhook URL here
    
    logger.info("🐋 Whale Tracker started - monitoring BTC and ETH whale activity...")
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Update prices
                await asyncio.gather(
                    btc_monitor.get_btc_price(session),
                    eth_monitor.get_eth_price(session)
                )
                
                logger.info("Current prices - BTC: $%.2f, ETH: $%.2f", btc_monitor.btc_price, eth_monitor.eth_price)
                
                # Monitor all sources (US-friendly exchanges)
                results = await asyncio.gather(
                    btc_monitor.fetch_large_transactions(session),
                    btc_monitor.monitor_mempool(session),
                    eth_monitor.fetch_large_eth_transfers(session),
                    exchange_monitor.monitor_coinbase_pro_orderbook(session, 'BTC-USD'),
                    exchange_monitor.monitor_coinbase_pro_orderbook(session, 'ETH-USD'),
                    exchange_monitor.monitor_kraken_orderbook(session, 'BTCUSD'),
                    exchange_monitor.monitor_kraken_orderbook(session, 'ETHUSD'),
                    exchange_monitor.monitor_gemini_orderbook(session, 'btcusd'),
                    exchange_monitor.monitor_gemini_orderbook(session, 'ethusd'),
                    return_exceptions=True
                )
                
                # Process and alert on all whale activities
                for result in results:
                    if isinstance(result, list):
                        for whale_activity in result:
                            await alert_system.send_alert(session, whale_activity)
                            logger.info("🐋 Whale detected: %s - $%.2f", whale_activity['type'], whale_activity['usd_value'])
                
                # Wait before next scan
                await asyncio.sleep(30)  # Scan every 30 seconds
                
            except KeyboardInterrupt:
                logger.info("Whale tracker stopped by user")
                break
            except (aiohttp.ClientError, KeyError, ValueError) as e:
                logger.error("Error in main loop: %s", e)
                await asyncio.sleep(60)  # Wait longer on error


if __name__ == "__main__":
    asyncio.run(main())
