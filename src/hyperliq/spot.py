from enum import StrEnum
from hyperliquid.utils import constants
import requests
import json
from typing import Callable, Optional, Dict, Any

from hyperliq.order import Side

SPOT_ASSET_ID_OFFSET = 10000


class HyperliquidSpot(object):
    def __init__(self, address, info, exchange):
        """
        Parameters:
        address (str): The user's wallet address on the Hyperliquid platform.
        info (object): An object to interact with Hyperliquid's API.
        exchange (object): An object representing the exchange for spot trading operations.
        """
        self.address = address
        self.info = info
        self.exchange = exchange
        self._spot_meta_data = None

    def get_spot_meta_data(self):
        """
        Retrieves meta data for all tradeable spot assets on Hyperliquid
        
        Returns:
        dict: Meta data containing spot universe and asset contexts
        """
        if self._spot_meta_data is None:
            url = constants.TESTNET_API_URL + "/info"
            headers = {"Content-Type": "application/json"}
            body = {
                "type": "spotMeta",
            }
            
            response = requests.post(url, headers=headers, data=json.dumps(body))
            self._spot_meta_data = response.json()
        return self._spot_meta_data

    def get_spot_balances(self):
        """
        Get all spot balances for the user
        
        Returns:
        dict: Dictionary containing spot token balances
        """
        spot_user_state = self.info.spot_user_state(self.address)
        balances = spot_user_state.get("balances", [])
        
        # Convert to more readable format
        balance_dict = {}
        for balance in balances:
            token = balance.get("coin", "")
            amount = float(balance.get("hold", 0))
            if amount > 0:
                balance_dict[token] = amount
        
        return balance_dict

    def create_spot_market_order(
        self,
        symbol: str,
        order_quantity: float,
        side: Side,
    ):
        """
        Creates a spot market order on Hyperliquid.
        
        Note: For spot assets, use asset index + 10000.
        For example, PURR/USDC would use 10000 since PURR has index 0 in spot metadata.

        Parameters:
        symbol (str): The trading symbol for the order (e.g., "PURR/USDC").
        order_quantity (float): The quantity of the asset to be ordered.
        side (Side): The order side, either BUY or SELL.

        Returns:
        dict: The response from the Hyperliquid platform after creating the market order.
        """
        asset_index = self._get_spot_asset_index(symbol)
        if asset_index is None:
            raise ValueError(f"Symbol {symbol} not found in spot metadata")
        
        # Convert to spot asset ID (index + 10000)
        spot_asset_id = asset_index + SPOT_ASSET_ID_OFFSET
        
        is_buy = side == Side.BUY
        
        # Use the exchange's order method for spot trading
        order_result = self.exchange.order(
            spot_asset_id, is_buy, order_quantity, None, {"market": {}}
        )
        
        return order_result

    def create_spot_limit_order(
        self, 
        symbol: str, 
        order_quantity: float, 
        side: Side, 
        limit_price: float
    ):
        """
        Creates a spot limit order on Hyperliquid.

        Parameters:
        symbol (str): The trading symbol for the order (e.g., "PURR/USDC").
        order_quantity (float): The quantity of the asset to be ordered.
        side (Side): The order side, either BUY or SELL.
        limit_price (float): The limit price for the order.

        Returns:
        dict: The response from the Hyperliquid platform after creating the limit order.
        """
        asset_index = self._get_spot_asset_index(symbol)
        if asset_index is None:
            raise ValueError(f"Symbol {symbol} not found in spot metadata")
        
        # Convert to spot asset ID (index + 10000)
        spot_asset_id = asset_index + SPOT_ASSET_ID_OFFSET
        
        is_buy = side == Side.BUY
        
        order_result = self.exchange.order(
            spot_asset_id, is_buy, order_quantity, limit_price, {"limit": {"tif": "Gtc"}}
        )
        
        return order_result

    def spot_transfer(self, amount: float, destination: str, token: str):
        """
        Transfer spot tokens to another address
        
        Parameters:
        amount (float): Amount to transfer
        destination (str): Destination wallet address
        token (str): Token symbol to transfer
        
        Returns:
        dict: Transfer result
        """
        return self.exchange.spot_transfer(amount, destination, token)

    def get_spot_open_orders(self):
        """
        Get all open spot orders for the user
        
        Returns:
        list: List of open spot orders
        """
        all_orders = self.info.open_orders(self.address)
        # Filter for spot orders (asset IDs >= 10000)
        spot_orders = []
        for order in all_orders:
            if order.get("coin", 0) >= SPOT_ASSET_ID_OFFSET:
                spot_orders.append(order)
        
        return spot_orders

    def cancel_spot_order(self, asset_id: int, order_id: int):
        """
        Cancel a specific spot order
        
        Parameters:
        asset_id (int): The spot asset ID (index + 10000)
        order_id (int): The order ID to cancel
        
        Returns:
        dict: Cancellation result
        """
        return self.exchange.cancel(asset_id, order_id)

    def cancel_all_spot_orders(self):
        """
        Cancel all open spot orders for the user
        
        Returns:
        list: List of cancellation results
        """
        open_orders = self.get_spot_open_orders()
        results = []
        
        for order in open_orders:
            asset_id = order.get("coin")
            order_id = order.get("oid")
            if asset_id and order_id:
                result = self.cancel_spot_order(asset_id, order_id)
                results.append(result)
        
        return results

    def _get_spot_asset_index(self, symbol: str):
        """
        Helper method to get the asset index for a spot symbol
        
        Parameters:
        symbol (str): Trading pair symbol (e.g., "PURR/USDC")
        
        Returns:
        int: Asset index in spot metadata, or None if not found
        """
        try:
            spot_meta = self.get_spot_meta_data()
            spot_universe = spot_meta.get("universe", [])
            
            for index, asset in enumerate(spot_universe):
                asset_name = asset.get("name", "")
                if asset_name.upper() == symbol.upper():
                    return index
            
            return None
        except Exception as e:
            print(f"Error getting spot asset index: {e}")
            return None

    def get_spot_market_data(self, symbol: str):
        """
        Get current market data for a spot symbol
        
        Parameters:
        symbol (str): Trading pair symbol
        
        Returns:
        dict: Market data including price, volume, etc.
        """
        try:
            asset_index = self._get_spot_asset_index(symbol)
            if asset_index is None:
                return None
            
            spot_asset_id = asset_index + SPOT_ASSET_ID_OFFSET
            
            # Get level 2 book data
            l2_book = self.info.l2_snapshot(spot_asset_id)
            
            return l2_book
        except Exception as e:
            print(f"Error getting spot market data: {e}")
            return None

    def get_spot_top_of_book(self, symbol: str):
        """
        Get real-time top of book (best bid/ask) for a spot symbol
        
        Parameters:
        symbol (str): Trading pair symbol
        
        Returns:
        dict: Top of book data with best bid and ask
        """
        try:
            market_data = self.get_spot_market_data(symbol)
            if not market_data:
                return None
            
            levels = market_data.get("levels", [])
            if not levels:
                return None
            
            # Extract best bid and ask
            bids = levels[0].get("bid", [])
            asks = levels[0].get("ask", [])
            
            top_of_book = {}
            
            if bids:
                best_bid = bids[0]
                top_of_book["best_bid"] = {
                    "price": float(best_bid.get("px", 0)),
                    "size": float(best_bid.get("sz", 0)),
                    "n_orders": best_bid.get("n", 0)
                }
            
            if asks:
                best_ask = asks[0]
                top_of_book["best_ask"] = {
                    "price": float(best_ask.get("px", 0)),
                    "size": float(best_ask.get("sz", 0)),
                    "n_orders": best_ask.get("n", 0)
                }
            
            return top_of_book
            
        except Exception as e:
            print(f"Error getting spot top of book: {e}")
            return None

    def subscribe_spot_top_of_book(self, symbol: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to real-time top of book updates for a spot symbol via WebSocket
        
        Parameters:
        symbol (str): Trading pair symbol
        callback (function): Callback function to handle real-time updates
        
        Returns:
        str: Subscription ID if successful, None otherwise
        """
        try:
            asset_index = self._get_spot_asset_index(symbol)
            if asset_index is None:
                print(f"Symbol {symbol} not found in spot metadata")
                return None
            
            spot_asset_id = asset_index + SPOT_ASSET_ID_OFFSET
            
            # Subscribe to BBO (Best Bid Offer) for real-time top of book
            subscription = {
                "type": "bbo",
                "coin": spot_asset_id
            }
            
            def bbo_callback(message):
                """Process BBO message and extract top of book data"""
                try:
                    if message.get("channel") == "bbo":
                        data = message.get("data", {})
                        top_of_book = {
                            "symbol": symbol,
                            "timestamp": data.get("time", 0),
                            "best_bid": None,
                            "best_ask": None
                        }
                        
                        bbo_data = data.get("bbo", [])
                        if len(bbo_data) >= 2:
                            # BBO format: [bid_levels, ask_levels]
                            bid_levels = bbo_data[0]
                            ask_levels = bbo_data[1]
                            
                            if bid_levels:
                                best_bid = bid_levels[0]
                                top_of_book["best_bid"] = {
                                    "price": float(best_bid.get("px", 0)),
                                    "size": float(best_bid.get("sz", 0)),
                                    "n_orders": best_bid.get("n", 0)
                                }
                            
                            if ask_levels:
                                best_ask = ask_levels[0]
                                top_of_book["best_ask"] = {
                                    "price": float(best_ask.get("px", 0)),
                                    "size": float(best_ask.get("sz", 0)),
                                    "n_orders": best_ask.get("n", 0)
                                }
                        
                        callback(top_of_book)
                        
                except Exception as e:
                    print(f"Error processing BBO message: {e}")
            
            # Subscribe using the info object's WebSocket manager
            subscription_id = self.info.subscribe(subscription, bbo_callback)
            return subscription_id
            
        except Exception as e:
            print(f"Error subscribing to spot top of book: {e}")
            return None

    def subscribe_spot_l2_book(self, symbol: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to real-time L2 order book updates for a spot symbol
        
        Parameters:
        symbol (str): Trading pair symbol
        callback (function): Callback function to handle real-time updates
        
        Returns:
        str: Subscription ID if successful, None otherwise
        """
        try:
            asset_index = self._get_spot_asset_index(symbol)
            if asset_index is None:
                print(f"Symbol {symbol} not found in spot metadata")
                return None
            
            spot_asset_id = asset_index + SPOT_ASSET_ID_OFFSET
            
            # Subscribe to L2 book updates
            subscription = {
                "type": "l2Book",
                "coin": spot_asset_id
            }
            
            def l2_callback(message):
                """Process L2 book message"""
                try:
                    if message.get("channel") == "l2Book":
                        data = message.get("data", {})
                        book_data = {
                            "symbol": symbol,
                            "timestamp": data.get("time", 0),
                            "levels": data.get("levels", []),
                            "coin": data.get("coin", "")
                        }
                        callback(book_data)
                        
                except Exception as e:
                    print(f"Error processing L2 book message: {e}")
            
            subscription_id = self.info.subscribe(subscription, l2_callback)
            return subscription_id
            
        except Exception as e:
            print(f"Error subscribing to spot L2 book: {e}")
            return None

    def unsubscribe(self, subscription_id: str):
        """
        Unsubscribe from a WebSocket subscription
        
        Parameters:
        subscription_id (str): The subscription ID to unsubscribe from
        
        Returns:
        bool: True if successful, False otherwise
        """
        try:
            return self.info.unsubscribe(subscription_id)
        except Exception as e:
            print(f"Error unsubscribing: {e}")
            return False