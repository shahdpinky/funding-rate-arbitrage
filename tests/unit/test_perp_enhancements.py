#!/usr/bin/env python3
"""
Unit tests for enhanced Hyperliquid perpetual trading functionality
"""
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'hyperliq'))

from hyperliq.order import HyperLiquidOrder, Side


class TestHyperLiquidOrderEnhancements(unittest.TestCase):
    """Test the new real-time market data methods added to HyperLiquidOrder"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_address = "0x1234567890abcdef"
        self.mock_info = Mock()
        self.mock_exchange = Mock()
        
        self.order = HyperLiquidOrder(
            address=self.mock_address,
            info=self.mock_info,
            exchange=self.mock_exchange
        )

    def test_get_perp_top_of_book_success(self):
        """Test successful perpetual top of book retrieval"""
        # Mock L2 snapshot response
        mock_l2_data = {
            "levels": [
                {
                    "bid": [{"px": "45000.5", "sz": "2.5", "n": 10}],
                    "ask": [{"px": "45001.0", "sz": "1.8", "n": 7}]
                }
            ]
        }
        self.mock_info.l2_snapshot.return_value = mock_l2_data
        
        result = self.order.get_perp_top_of_book("BTC")
        
        # Verify API call
        self.mock_info.l2_snapshot.assert_called_once_with("BTC")
        
        # Verify result structure
        expected = {
            "best_bid": {"price": 45000.5, "size": 2.5, "n_orders": 10},
            "best_ask": {"price": 45001.0, "size": 1.8, "n_orders": 7}
        }
        self.assertEqual(result, expected)

    def test_get_perp_top_of_book_no_data(self):
        """Test perpetual top of book with no market data"""
        self.mock_info.l2_snapshot.return_value = None
        
        result = self.order.get_perp_top_of_book("BTC")
        
        self.assertIsNone(result)

    def test_get_perp_top_of_book_empty_levels(self):
        """Test perpetual top of book with empty levels"""
        mock_l2_data = {"levels": []}
        self.mock_info.l2_snapshot.return_value = mock_l2_data
        
        result = self.order.get_perp_top_of_book("BTC")
        
        self.assertIsNone(result)

    def test_get_perp_top_of_book_partial_data(self):
        """Test perpetual top of book with only bid or ask"""
        # Only bid data
        mock_l2_data = {
            "levels": [
                {
                    "bid": [{"px": "45000.5", "sz": "2.5", "n": 10}],
                    "ask": []
                }
            ]
        }
        self.mock_info.l2_snapshot.return_value = mock_l2_data
        
        result = self.order.get_perp_top_of_book("BTC")
        
        expected = {
            "best_bid": {"price": 45000.5, "size": 2.5, "n_orders": 10}
        }
        self.assertEqual(result, expected)

    def test_get_perp_top_of_book_exception(self):
        """Test perpetual top of book with exception"""
        self.mock_info.l2_snapshot.side_effect = Exception("API error")
        
        result = self.order.get_perp_top_of_book("BTC")
        
        self.assertIsNone(result)

    def test_subscribe_perp_top_of_book_success(self):
        """Test successful perpetual BBO WebSocket subscription"""
        self.mock_info.subscribe.return_value = "perp_bbo_123"
        
        callback = Mock()
        result = self.order.subscribe_perp_top_of_book("ETH", callback)
        
        # Verify subscription call
        expected_subscription = {"type": "bbo", "coin": "ETH"}
        self.mock_info.subscribe.assert_called_once()
        call_args = self.mock_info.subscribe.call_args[0]
        self.assertEqual(call_args[0], expected_subscription)
        
        # Verify subscription ID returned
        self.assertEqual(result, "perp_bbo_123")

    def test_subscribe_perp_top_of_book_callback_processing(self):
        """Test BBO callback message processing"""
        callback = Mock()
        
        # Capture the callback function passed to subscribe
        def mock_subscribe(subscription, callback_func):
            # Simulate receiving a BBO message
            mock_message = {
                "channel": "bbo",
                "data": {
                    "time": 1234567890,
                    "bbo": [
                        [{"px": "3500.5", "sz": "10.0", "n": 5}],  # bids
                        [{"px": "3501.0", "sz": "8.0", "n": 3}]   # asks
                    ]
                }
            }
            callback_func(mock_message)
            return "sub_123"
        
        self.mock_info.subscribe.side_effect = mock_subscribe
        
        result = self.order.subscribe_perp_top_of_book("ETH", callback)
        
        # Verify callback was called with processed data
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        
        expected = {
            "symbol": "ETH",
            "timestamp": 1234567890,
            "best_bid": {"price": 3500.5, "size": 10.0, "n_orders": 5},
            "best_ask": {"price": 3501.0, "size": 8.0, "n_orders": 3}
        }
        self.assertEqual(call_args, expected)

    def test_subscribe_perp_top_of_book_exception(self):
        """Test perpetual BBO subscription with exception"""
        self.mock_info.subscribe.side_effect = Exception("WebSocket error")
        
        callback = Mock()
        result = self.order.subscribe_perp_top_of_book("BTC", callback)
        
        self.assertIsNone(result)

    def test_subscribe_perp_l2_book_success(self):
        """Test successful perpetual L2 book WebSocket subscription"""
        self.mock_info.subscribe.return_value = "perp_l2_456"
        
        callback = Mock()
        result = self.order.subscribe_perp_l2_book("SOL", callback)
        
        # Verify subscription call
        expected_subscription = {"type": "l2Book", "coin": "SOL"}
        self.mock_info.subscribe.assert_called_once()
        call_args = self.mock_info.subscribe.call_args[0]
        self.assertEqual(call_args[0], expected_subscription)
        
        # Verify subscription ID returned
        self.assertEqual(result, "perp_l2_456")

    def test_subscribe_perp_l2_book_callback_processing(self):
        """Test L2 book callback message processing"""
        callback = Mock()
        
        def mock_subscribe(subscription, callback_func):
            mock_message = {
                "channel": "l2Book",
                "data": {
                    "time": 1234567890,
                    "coin": "SOL",
                    "levels": [
                        {"bid": [{"px": "100.5", "sz": "50.0"}], "ask": [{"px": "101.0", "sz": "30.0"}]}
                    ]
                }
            }
            callback_func(mock_message)
            return "sub_456"
        
        self.mock_info.subscribe.side_effect = mock_subscribe
        
        result = self.order.subscribe_perp_l2_book("SOL", callback)
        
        # Verify callback was called with processed data
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        
        expected = {
            "symbol": "SOL",
            "timestamp": 1234567890,
            "levels": [{"bid": [{"px": "100.5", "sz": "50.0"}], "ask": [{"px": "101.0", "sz": "30.0"}]}],
            "coin": "SOL"
        }
        self.assertEqual(call_args, expected)

    def test_unsubscribe_success(self):
        """Test successful WebSocket unsubscription"""
        self.mock_info.unsubscribe.return_value = True
        
        result = self.order.unsubscribe("sub_789")
        
        self.mock_info.unsubscribe.assert_called_once_with("sub_789")
        self.assertTrue(result)

    def test_unsubscribe_exception(self):
        """Test WebSocket unsubscription with exception"""
        self.mock_info.unsubscribe.side_effect = Exception("Unsubscribe failed")
        
        result = self.order.unsubscribe("sub_789")
        
        self.assertFalse(result)

    def test_callback_error_handling(self):
        """Test that callback errors don't break subscription processing"""
        def mock_subscribe(subscription, callback_func):
            # Simulate malformed message
            mock_message = {"invalid": "data"}
            callback_func(mock_message)
            return "sub_error"
        
        self.mock_info.subscribe.side_effect = mock_subscribe
        
        callback = Mock()
        result = self.order.subscribe_perp_top_of_book("BTC", callback)
        
        # Subscription should still succeed
        self.assertEqual(result, "sub_error")
        
        # Callback should not have been called due to invalid message format
        callback.assert_not_called()

    def test_bbo_callback_partial_data(self):
        """Test BBO callback with partial bid/ask data"""
        callback = Mock()
        
        def mock_subscribe(subscription, callback_func):
            # Message with only bid data
            mock_message = {
                "channel": "bbo",
                "data": {
                    "time": 1234567890,
                    "bbo": [
                        [{"px": "50000.0", "sz": "1.0", "n": 1}],  # bids
                        []  # no asks
                    ]
                }
            }
            callback_func(mock_message)
            return "sub_partial"
        
        self.mock_info.subscribe.side_effect = mock_subscribe
        
        result = self.order.subscribe_perp_top_of_book("BTC", callback)
        
        # Verify callback received partial data
        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        
        self.assertEqual(call_args["best_bid"]["price"], 50000.0)
        self.assertIsNone(call_args["best_ask"])


class TestExistingMethodsIntegrity(unittest.TestCase):
    """Test that existing, unmodified methods still behave as expected"""

    def setUp(self):
        """Set up test fixtures for existing methods"""
        self.mock_address = "0xabcdef1234567890"
        self.mock_info = Mock()
        self.mock_exchange = Mock()
        self.order = HyperLiquidOrder(self.mock_address, self.mock_info, self.mock_exchange)

    def test_create_market_order_still_works(self):
        """Test that existing create_market_order method is unaffected"""
        # Mock a successful order response
        mock_response = {
            "status": "ok",
            "response": {
                "type": "order",
                "data": {
                    "statuses": [{"filled": {"oid": 123, "totalSz": "0.1", "avgPx": "50000"}}]
                }
            }
        }
        self.mock_exchange.market_open.return_value = mock_response
        
        result = self.order.create_market_order("BTC", 0.1, Side.BUY)
        
        self.mock_exchange.market_open.assert_called_once_with("BTC", True, 0.1, None, 0.01)
        self.assertTrue(result)

    def test_get_all_positions_still_works(self):
        """Test that existing get_all_positions method is unaffected"""
        mock_user_state = {
            "assetPositions": [
                {"position": {"coin": "BTC", "szi": "0.5"}},
                {"position": {"coin": "ETH", "szi": "0.0"}},
                {"position": {"coin": "SOL", "szi": "-2.0"}}
            ]
        }
        self.mock_info.user_state.return_value = mock_user_state
        
        result = self.order.get_all_positions()
        
        expected = [
            {"symbol": "BTC", "position_size": 0.5},
            {"symbol": "SOL", "position_size": -2.0}
        ]
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)