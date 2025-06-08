from enum import StrEnum
import hyperliq_utils as hyperliq_utils
from typing import Callable, Optional, Dict, Any


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class HyperLiquidOrder(object):
    def __init__(self, address, info, exchange):
        """
        Parameters:
        address (str): The user's wallet address on the Hyperliquid platform.
        info (object): An object to interact with Hyperliquid's API.
        exchange (object): An object representing the exchange for order-related operations.
        """
        self.address = address
        self.info = info
        self.exchange = exchange

    def create_market_order(
        self,
        symbol: str,
        order_quantity: float,
        side: Side,
        slippage: float = 0.01,
    ):
        """
        Creates a market order on Hyperliquid.

        Parameters:
        symbol (str): The trading symbol for the order (e.g., "BTC-USD").
        order_quantity (float): The quantity of the asset to be ordered.
        side (Side): The order side, either BUY or SELL.
        slippage (float): The allowable slippage in percentage.

        Returns:
        bool: True if the order was successful, False otherwise.
        """
        is_buy = side == Side.BUY
        order_result = self.exchange.market_open(
            symbol, is_buy, order_quantity, None, slippage
        )

        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    print(
                        f'Hyperliquid Order #{filled["oid"]} filled {filled["totalSz"]} @{filled["avgPx"]}'
                    )
                    return True
                except KeyError:
                    print(f'Error: {status["error"]}')
                    return False
        return False

    def create_limit_order(
        self, symbol: str, order_quantity: float, side: Side, limit_price: float
    ):
        """
        Creates a limit order on Hyperliquid.

        Parameters:
        symbol (str): The trading symbol for the order (e.g., "BTC-USD").
        order_quantity (float): The quantity of the asset to be ordered.
        side (Side): The order side, either BUY or SELL.
        limit_price (float): The limit price for the order.

        Returns:
        dict: The response from the Hyperliquid platform after creating the limit order.
        """

        is_buy = side == Side.BUY
        order_result = self.exchange.order(
            symbol, is_buy, order_quantity, limit_price, {"limit": {"tif": "Gtc"}}
        )
        print(order_result)

    def market_close_an_asset(self, symbol):
        """
        Closes an open market position for a given asset on Hyperliquid.

        Parameters:
        symbol (str): The trading symbol of the asset to be closed (e.g., "BTC-USD").

        Returns: Bool if order is successful
        """
        order_result = self.exchange.market_close(symbol)

        if order_result["status"] == "ok":
            for status in order_result["response"]["data"]["statuses"]:
                try:
                    filled = status["filled"]
                    print(
                        f'Hyperliquid Order #{filled["oid"]} filled {filled["totalSz"]} @{filled["avgPx"]}'
                    )
                    return True
                except KeyError:
                    print(f'Error: {status["error"]}')
                    return False

    def cancel_open_orders(self):
        open_orders = self.info.open_orders(self.address)
        for open_order in open_orders:
            print(f"cancelling order {open_order}")
            self.exchange.cancel(open_order["coin"], open_order["oid"])

    def get_all_positions(self):
        """
        Get all Hyperliquid open positions

        returns: a list of dicts with symbols and position size
        """
        # Get the user state and print out position information
        user_state = self.info.user_state(self.address)
        filtered_positions = []
        for position in user_state["assetPositions"]:
            symbol = position["position"]["coin"]
            position_size = float(position["position"]["szi"])
            if position_size != 0:
                filtered_positions.append(
                    {"symbol": symbol, "position_size": position_size}
                )

        if len(filtered_positions) == 0:
            print("     No open positions")

        return filtered_positions

    def get_perp_top_of_book(self, symbol: str):
        """
        Get real-time top of book (best bid/ask) for a perpetual symbol
        
        Parameters:
        symbol (str): Trading symbol (e.g., "BTC", "ETH")
        
        Returns:
        dict: Top of book data with best bid and ask
        """
        try:
            # Get level 2 book data for perpetual
            l2_book = self.info.l2_snapshot(symbol)
            
            if not l2_book:
                return None
            
            levels = l2_book.get("levels", [])
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
            print(f"Error getting perp top of book: {e}")
            return None

    def subscribe_perp_top_of_book(self, symbol: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to real-time top of book updates for a perpetual symbol via WebSocket
        
        Parameters:
        symbol (str): Trading symbol (e.g., "BTC", "ETH")
        callback (function): Callback function to handle real-time updates
        
        Returns:
        str: Subscription ID if successful, None otherwise
        """
        try:
            # Subscribe to BBO (Best Bid Offer) for real-time top of book
            subscription = {
                "type": "bbo",
                "coin": symbol
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
            print(f"Error subscribing to perp top of book: {e}")
            return None

    def subscribe_perp_l2_book(self, symbol: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to real-time L2 order book updates for a perpetual symbol
        
        Parameters:
        symbol (str): Trading symbol (e.g., "BTC", "ETH")
        callback (function): Callback function to handle real-time updates
        
        Returns:
        str: Subscription ID if successful, None otherwise
        """
        try:
            # Subscribe to L2 book updates
            subscription = {
                "type": "l2Book",
                "coin": symbol
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
            print(f"Error subscribing to perp L2 book: {e}")
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
