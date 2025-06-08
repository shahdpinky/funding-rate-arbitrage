#!/usr/bin/env python3
"""
Unit tests for Hyperliquid spot trading functionality
"""
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'hyperliq'))

from hyperliq.spot import HyperliquidSpot, Side


class TestHyperliquidSpot(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_address = "0x1234567890abcdef"
        self.mock_info = Mock()
        self.mock_exchange = Mock()
        
        self.spot = HyperliquidSpot(
            address=self.mock_address,
            info=self.mock_info,
            exchange=self.mock_exchange
        )

    def test_init(self):
        """Test HyperliquidSpot initialization"""
        self.assertEqual(self.spot.address, self.mock_address)
        self.assertEqual(self.spot.info, self.mock_info)
        self.assertEqual(self.spot.exchange, self.mock_exchange)

    @patch('requests.post')
    def test_get_spot_meta_data_success(self, mock_post):
        """Test successful spot metadata retrieval"""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "universe": [
                {"name": "PURR/USDC", "index": 0},
                {"name": "TEST/USDC", "index": 1}
            ]
        }
        mock_post.return_value = mock_response
        
        result = self.spot.get_spot_meta_data()
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        # Check positional args for URL
        args, kwargs = call_args
        self.assertIn("/info", args[0])
        self.assertEqual(kwargs["headers"]["Content-Type"], "application/json")
        
        # Verify request body
        body = json.loads(kwargs["data"])
        self.assertEqual(body["type"], "spotMeta")
        
        # Verify result
        self.assertEqual(result["universe"][0]["name"], "PURR/USDC")

    def test_get_spot_balances_success(self):
        """Test successful spot balance retrieval"""
        # Mock spot user state
        mock_user_state = {
            "balances": [
                {"coin": "USDC", "hold": "1000.5"},
                {"coin": "PURR", "hold": "50.0"},
                {"coin": "EMPTY", "hold": "0.0"}
            ]
        }
        self.mock_info.spot_user_state.return_value = mock_user_state
        
        result = self.spot.get_spot_balances()
        
        # Verify API call
        self.mock_info.spot_user_state.assert_called_once_with(self.mock_address)
        
        # Verify result (should exclude zero balances)
        expected = {"USDC": 1000.5, "PURR": 50.0}
        self.assertEqual(result, expected)

    def test_get_spot_balances_empty(self):
        """Test spot balance retrieval with no balances"""
        self.mock_info.spot_user_state.return_value = {"balances": []}
        
        result = self.spot.get_spot_balances()
        
        self.assertEqual(result, {})

    @patch.object(HyperliquidSpot, '_get_spot_asset_index')
    def test_create_spot_market_order_success(self, mock_get_index):
        """Test successful spot market order creation"""
        # Setup mocks
        mock_get_index.return_value = 0
        self.mock_exchange.order.return_value = {
            "status": "ok",
            "response": {"data": {"statuses": [{"filled": {"oid": 123, "totalSz": "1.0", "avgPx": "100.0"}}]}}
        }
        
        result = self.spot.create_spot_market_order("PURR/USDC", 1.0, Side.BUY)
        
        # Verify asset index lookup
        mock_get_index.assert_called_once_with("PURR/USDC")
        
        # Verify order call (asset ID should be 0 + 10000 = 10000)
        self.mock_exchange.order.assert_called_once_with(
            10000,  # spot asset ID
            True,   # is_buy
            1.0,    # quantity
            None,   # price (market order)
            {"market": {}}
        )
        
        # Verify result
        self.assertEqual(result["status"], "ok")

    @patch.object(HyperliquidSpot, '_get_spot_asset_index')
    def test_create_spot_market_order_invalid_symbol(self, mock_get_index):
        """Test spot market order with invalid symbol"""
        mock_get_index.return_value = None
        
        with self.assertRaises(ValueError) as cm:
            self.spot.create_spot_market_order("INVALID/USDC", 1.0, Side.BUY)
        
        self.assertIn("not found in spot metadata", str(cm.exception))

    @patch.object(HyperliquidSpot, '_get_spot_asset_index')
    def test_create_spot_limit_order_success(self, mock_get_index):
        """Test successful spot limit order creation"""
        mock_get_index.return_value = 1
        self.mock_exchange.order.return_value = {"status": "ok"}
        
        result = self.spot.create_spot_limit_order("TEST/USDC", 2.0, Side.SELL, 50.0)
        
        # Verify order call
        self.mock_exchange.order.assert_called_once_with(
            10001,  # spot asset ID (1 + 10000)
            False,  # is_buy (SELL)
            2.0,    # quantity
            50.0,   # limit price
            {"limit": {"tif": "Gtc"}}
        )

    def test_spot_transfer(self):
        """Test spot token transfer"""
        self.mock_exchange.spot_transfer.return_value = {"status": "ok"}
        
        result = self.spot.spot_transfer(100.0, "0xdestination", "USDC")
        
        self.mock_exchange.spot_transfer.assert_called_once_with(100.0, "0xdestination", "USDC")
        self.assertEqual(result["status"], "ok")

    def test_get_spot_open_orders(self):
        """Test getting spot open orders (filters asset IDs >= 10000)"""
        mock_orders = [
            {"coin": 1, "oid": 123},      # Perpetual order (< 10000)
            {"coin": 10000, "oid": 456},  # Spot order
            {"coin": 10001, "oid": 789}   # Spot order
        ]
        self.mock_info.open_orders.return_value = mock_orders
        
        result = self.spot.get_spot_open_orders()
        
        # Should only return spot orders (asset IDs >= 10000)
        expected = [{"coin": 10000, "oid": 456}, {"coin": 10001, "oid": 789}]
        self.assertEqual(result, expected)

    def test_cancel_spot_order(self):
        """Test canceling a specific spot order"""
        self.mock_exchange.cancel.return_value = {"status": "ok"}
        
        result = self.spot.cancel_spot_order(10000, 123)
        
        self.mock_exchange.cancel.assert_called_once_with(10000, 123)
        self.assertEqual(result["status"], "ok")

    @patch.object(HyperliquidSpot, 'get_spot_open_orders')
    @patch.object(HyperliquidSpot, 'cancel_spot_order')
    def test_cancel_all_spot_orders(self, mock_cancel, mock_get_orders):
        """Test canceling all spot orders"""
        mock_orders = [
            {"coin": 10000, "oid": 456},
            {"coin": 10001, "oid": 789}
        ]
        mock_get_orders.return_value = mock_orders
        mock_cancel.return_value = {"status": "ok"}
        
        result = self.spot.cancel_all_spot_orders()
        
        # Verify all orders were canceled
        self.assertEqual(mock_cancel.call_count, 2)
        mock_cancel.assert_any_call(10000, 456)
        mock_cancel.assert_any_call(10001, 789)
        
        # Verify results
        self.assertEqual(len(result), 2)
        self.assertTrue(all(r["status"] == "ok" for r in result))

    @patch.object(HyperliquidSpot, 'get_spot_meta_data')
    def test_get_spot_asset_index_success(self, mock_get_meta):
        """Test successful asset index lookup"""
        mock_meta = {
            "universe": [
                {"name": "PURR/USDC"},
                {"name": "TEST/USDC"}
            ]
        }
        mock_get_meta.return_value = mock_meta
        
        result = self.spot._get_spot_asset_index("TEST/USDC")
        
        self.assertEqual(result, 1)

    @patch.object(HyperliquidSpot, 'get_spot_meta_data')
    def test_get_spot_asset_index_not_found(self, mock_get_meta):
        """Test asset index lookup for non-existent symbol"""
        mock_meta = {"universe": [{"name": "PURR/USDC"}]}
        mock_get_meta.return_value = mock_meta
        
        result = self.spot._get_spot_asset_index("INVALID/USDC")
        
        self.assertIsNone(result)

    @patch.object(HyperliquidSpot, 'get_spot_meta_data')
    def test_get_spot_asset_index_exception(self, mock_get_meta):
        """Test asset index lookup with exception"""
        mock_get_meta.side_effect = Exception("API error")
        
        result = self.spot._get_spot_asset_index("TEST/USDC")
        
        self.assertIsNone(result)

    @patch.object(HyperliquidSpot, 'get_spot_market_data')
    def test_get_spot_top_of_book_success(self, mock_get_market_data):
        """Test successful top of book retrieval"""
        mock_market_data = {
            "levels": [
                {
                    "bid": [{"px": "99.5", "sz": "10.0", "n": 5}],
                    "ask": [{"px": "100.5", "sz": "15.0", "n": 3}]
                }
            ]
        }
        mock_get_market_data.return_value = mock_market_data
        
        result = self.spot.get_spot_top_of_book("TEST/USDC")
        
        expected = {
            "best_bid": {"price": 99.5, "size": 10.0, "n_orders": 5},
            "best_ask": {"price": 100.5, "size": 15.0, "n_orders": 3}
        }
        self.assertEqual(result, expected)

    @patch.object(HyperliquidSpot, 'get_spot_market_data')
    def test_get_spot_top_of_book_no_data(self, mock_get_market_data):
        """Test top of book with no market data"""
        mock_get_market_data.return_value = None
        
        result = self.spot.get_spot_top_of_book("TEST/USDC")
        
        self.assertIsNone(result)

    @patch.object(HyperliquidSpot, '_get_spot_asset_index')
    def test_subscribe_spot_top_of_book_success(self, mock_get_index):
        """Test successful WebSocket BBO subscription"""
        mock_get_index.return_value = 0
        self.mock_info.subscribe.return_value = "sub_123"
        
        callback = Mock()
        result = self.spot.subscribe_spot_top_of_book("PURR/USDC", callback)
        
        # Verify subscription call
        expected_subscription = {"type": "bbo", "coin": 10000}
        self.mock_info.subscribe.assert_called_once()
        call_args = self.mock_info.subscribe.call_args[0]
        self.assertEqual(call_args[0], expected_subscription)
        
        # Verify subscription ID returned
        self.assertEqual(result, "sub_123")

    @patch.object(HyperliquidSpot, '_get_spot_asset_index')
    def test_subscribe_spot_top_of_book_invalid_symbol(self, mock_get_index):
        """Test WebSocket BBO subscription with invalid symbol"""
        mock_get_index.return_value = None
        
        callback = Mock()
        result = self.spot.subscribe_spot_top_of_book("INVALID/USDC", callback)
        
        self.assertIsNone(result)
        self.mock_info.subscribe.assert_not_called()

    def test_unsubscribe_success(self):
        """Test successful WebSocket unsubscription"""
        self.mock_info.unsubscribe.return_value = True
        
        result = self.spot.unsubscribe("sub_123")
        
        self.mock_info.unsubscribe.assert_called_once_with("sub_123")
        self.assertTrue(result)

    def test_unsubscribe_exception(self):
        """Test WebSocket unsubscription with exception"""
        self.mock_info.unsubscribe.side_effect = Exception("Unsubscribe error")
        
        result = self.spot.unsubscribe("sub_123")
        
        self.assertFalse(result)


class TestSideEnum(unittest.TestCase):
    """Test the Side enum"""
    
    def test_side_values(self):
        """Test Side enum values"""
        self.assertEqual(str(Side.BUY), "BUY")
        self.assertEqual(str(Side.SELL), "SELL")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)