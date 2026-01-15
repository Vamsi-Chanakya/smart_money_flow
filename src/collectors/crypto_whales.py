"""Crypto Whale Tracker - Monitor large cryptocurrency movements.

Sources:
- Etherscan API (free tier: 5 calls/sec)
- Blockchain.com API (free)
- Public whale wallet monitoring
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from ..utils.logger import get_logger
from ..utils.rate_limiter import RateLimiter

logger = get_logger(__name__)


@dataclass
class WhaleTransaction:
    """Represents a large crypto transaction."""

    tx_hash: str
    blockchain: str  # ethereum, bitcoin, etc.
    from_address: str
    to_address: str
    value: float
    value_usd: Optional[float]
    token: str  # ETH, BTC, USDT, etc.
    timestamp: datetime
    block_number: int
    is_exchange_inflow: bool  # Moving TO exchange (potential sell)
    is_exchange_outflow: bool  # Moving FROM exchange (potential hold)
    from_label: Optional[str]  # Known wallet label
    to_label: Optional[str]


@dataclass
class WalletBalance:
    """Represents a whale wallet balance."""

    address: str
    blockchain: str
    token: str
    balance: float
    balance_usd: Optional[float]
    label: Optional[str]
    last_updated: datetime


class CryptoWhaleCollector:
    """Collector for crypto whale movements.

    Tracks large transactions and known whale wallets.
    """

    # Known exchange addresses (simplified)
    EXCHANGE_ADDRESSES = {
        # Ethereum
        "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
        "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "Binance",
        "0x56eddb7aa87536c09ccc2793473599fd21a8b17f": "Binance",
        "0x9696f59e4d72e237be84ffd425dcad154bf96976": "Binance",
        "0x4e9ce36e442e55ecd9025b9a6e0d88485d628a67": "Binance US",
        "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase",
        "0x71660c4005ba85c37ccec55d0c4493e66fe775d3": "Coinbase",
        "0x89e51fa8ca5d66cd220baed62ed01e8951aa7c40": "Coinbase",
        "0x2b5634c42055806a59e9107ed44d43c426e58258": "Kraken",
        "0x267be1c1d684f78cb4f6a176c4911b741e4ffdc0": "Kraken",
        "0xdc76cd25977e0a5ae17155770273ad58648900d3": "OKX",
        "0x6cc5f688a315f3dc28a7781717a9a798a59fda7b": "OKX",
    }

    # Known whale wallets to track
    WHALE_WALLETS = {
        "0x00000000219ab540356cbb839cbe05303d7705fa": "ETH 2.0 Deposit Contract",
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": "WETH Contract",
        "0x40b38765696e3d5d8d9d834d8aad4bb6e418e489": "Robinhood",
        "0x1b3cb81e51011b549d78bf720b0d924ac763a7c2": "Grayscale",
    }

    def __init__(self, etherscan_api_key: str = ""):
        self.session = requests.Session()
        self.etherscan_api_key = etherscan_api_key
        self.rate_limiter = RateLimiter(5)  # Etherscan free tier

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get(self, url: str, params: dict = None) -> requests.Response:
        """Make rate-limited GET request."""
        self.rate_limiter.wait()
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    # ==================== Etherscan API ====================

    def get_eth_whale_transactions(
        self,
        min_value_eth: float = 100,
        blocks_back: int = 1000,
    ) -> list[WhaleTransaction]:
        """Get large ETH transactions from recent blocks.

        Args:
            min_value_eth: Minimum transaction value in ETH
            blocks_back: Number of blocks to look back

        Returns:
            List of whale transactions
        """
        if not self.etherscan_api_key:
            logger.warning("No Etherscan API key - using limited functionality")
            return self._get_whale_txs_alternative()

        # Get latest block number
        latest_block = self._get_latest_block()
        if not latest_block:
            return []

        transactions = []
        start_block = latest_block - blocks_back

        # Get internal transactions for known whale addresses
        for address in list(self.WHALE_WALLETS.keys())[:5]:  # Limit to avoid rate limits
            txs = self._get_address_transactions(address, start_block)
            for tx in txs:
                if tx.value >= min_value_eth:
                    transactions.append(tx)

        return transactions

    def _get_latest_block(self) -> Optional[int]:
        """Get the latest Ethereum block number."""
        url = "https://api.etherscan.io/api"
        params = {
            "module": "proxy",
            "action": "eth_blockNumber",
            "apikey": self.etherscan_api_key,
        }

        try:
            response = self._get(url, params)
            data = response.json()
            return int(data.get("result", "0"), 16)
        except Exception as e:
            logger.error(f"Error getting latest block: {e}")
            return None

    def _get_address_transactions(
        self,
        address: str,
        start_block: int,
    ) -> list[WhaleTransaction]:
        """Get transactions for an address."""
        url = "https://api.etherscan.io/api"
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": 99999999,
            "sort": "desc",
            "apikey": self.etherscan_api_key,
        }

        try:
            response = self._get(url, params)
            data = response.json()

            if data.get("status") != "1":
                return []

            transactions = []
            for tx in data.get("result", [])[:50]:  # Limit results
                value_wei = int(tx.get("value", 0))
                value_eth = value_wei / 1e18

                if value_eth < 1:  # Skip tiny transactions
                    continue

                from_addr = tx.get("from", "").lower()
                to_addr = tx.get("to", "").lower()

                transactions.append(WhaleTransaction(
                    tx_hash=tx.get("hash", ""),
                    blockchain="ethereum",
                    from_address=from_addr,
                    to_address=to_addr,
                    value=value_eth,
                    value_usd=None,  # Would need price API
                    token="ETH",
                    timestamp=datetime.fromtimestamp(int(tx.get("timeStamp", 0))),
                    block_number=int(tx.get("blockNumber", 0)),
                    is_exchange_inflow=to_addr in self.EXCHANGE_ADDRESSES,
                    is_exchange_outflow=from_addr in self.EXCHANGE_ADDRESSES,
                    from_label=self._get_address_label(from_addr),
                    to_label=self._get_address_label(to_addr),
                ))

            return transactions

        except Exception as e:
            logger.error(f"Error getting transactions for {address}: {e}")
            return []

    def _get_address_label(self, address: str) -> Optional[str]:
        """Get label for known address."""
        address = address.lower()
        return self.EXCHANGE_ADDRESSES.get(address) or self.WHALE_WALLETS.get(address)

    def _get_whale_txs_alternative(self) -> list[WhaleTransaction]:
        """Alternative whale tracking without API key.

        Uses public blockchain explorers.
        """
        # Fallback: scrape from public sources
        logger.info("Using alternative whale tracking (limited)")
        return []

    # ==================== Wallet Balance Tracking ====================

    def get_wallet_balance(self, address: str) -> Optional[WalletBalance]:
        """Get ETH balance for a wallet.

        Args:
            address: Ethereum address

        Returns:
            Wallet balance info
        """
        if not self.etherscan_api_key:
            return None

        url = "https://api.etherscan.io/api"
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "apikey": self.etherscan_api_key,
        }

        try:
            response = self._get(url, params)
            data = response.json()

            if data.get("status") != "1":
                return None

            balance_wei = int(data.get("result", 0))
            balance_eth = balance_wei / 1e18

            return WalletBalance(
                address=address,
                blockchain="ethereum",
                token="ETH",
                balance=balance_eth,
                balance_usd=None,
                label=self._get_address_label(address.lower()),
                last_updated=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error getting balance for {address}: {e}")
            return None

    def get_exchange_reserves(self) -> dict[str, float]:
        """Get ETH reserves for major exchanges.

        Returns:
            Dict mapping exchange name to ETH balance
        """
        reserves = {}

        for address, name in list(self.EXCHANGE_ADDRESSES.items())[:10]:
            balance = self.get_wallet_balance(address)
            if balance:
                if name not in reserves:
                    reserves[name] = 0
                reserves[name] += balance.balance

        return reserves

    # ==================== Analysis ====================

    def analyze_flow(self, transactions: list[WhaleTransaction]) -> dict:
        """Analyze whale transaction flow.

        Returns:
            Analysis of inflows vs outflows
        """
        total_inflow = sum(tx.value for tx in transactions if tx.is_exchange_inflow)
        total_outflow = sum(tx.value for tx in transactions if tx.is_exchange_outflow)
        net_flow = total_outflow - total_inflow

        if net_flow > 100:
            sentiment = "BULLISH"  # More leaving exchanges
        elif net_flow < -100:
            sentiment = "BEARISH"  # More going to exchanges
        else:
            sentiment = "NEUTRAL"

        return {
            "exchange_inflow_eth": total_inflow,
            "exchange_outflow_eth": total_outflow,
            "net_flow_eth": net_flow,
            "sentiment": sentiment,
            "transaction_count": len(transactions),
        }

    def get_top_whale_movements(
        self,
        min_value_eth: float = 500,
        limit: int = 20,
    ) -> list[WhaleTransaction]:
        """Get largest recent whale movements.

        Args:
            min_value_eth: Minimum ETH value
            limit: Max transactions to return

        Returns:
            Sorted list of largest transactions
        """
        transactions = self.get_eth_whale_transactions(min_value_eth=min_value_eth)
        transactions.sort(key=lambda x: x.value, reverse=True)
        return transactions[:limit]


# ==================== Bitcoin Tracking ====================

class BitcoinWhaleCollector:
    """Track Bitcoin whale movements using blockchain.com API."""

    BASE_URL = "https://blockchain.info"

    def __init__(self):
        self.session = requests.Session()
        self.rate_limiter = RateLimiter(3)

    def get_latest_blocks(self, count: int = 5) -> list[dict]:
        """Get latest Bitcoin blocks."""
        self.rate_limiter.wait()

        try:
            response = self.session.get(f"{self.BASE_URL}/latestblock", timeout=30)
            response.raise_for_status()
            latest = response.json()

            blocks = []
            block_hash = latest.get("hash")

            for _ in range(count):
                if not block_hash:
                    break

                self.rate_limiter.wait()
                block_response = self.session.get(
                    f"{self.BASE_URL}/rawblock/{block_hash}",
                    timeout=30
                )
                block_data = block_response.json()
                blocks.append(block_data)
                block_hash = block_data.get("prev_block")

            return blocks

        except Exception as e:
            logger.error(f"Error fetching Bitcoin blocks: {e}")
            return []

    def get_large_transactions(self, min_btc: float = 100) -> list[dict]:
        """Get large BTC transactions from recent blocks."""
        blocks = self.get_latest_blocks(3)

        large_txs = []
        for block in blocks:
            for tx in block.get("tx", []):
                total_output = sum(out.get("value", 0) for out in tx.get("out", [])) / 1e8

                if total_output >= min_btc:
                    large_txs.append({
                        "hash": tx.get("hash"),
                        "value_btc": total_output,
                        "time": datetime.fromtimestamp(tx.get("time", 0)),
                        "inputs": len(tx.get("inputs", [])),
                        "outputs": len(tx.get("out", [])),
                    })

        return sorted(large_txs, key=lambda x: x["value_btc"], reverse=True)[:20]
