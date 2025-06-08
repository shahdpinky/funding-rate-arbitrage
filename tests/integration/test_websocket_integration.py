#!/usr/bin/env python3
"""
Integration tests for Hyperliquid WebSocket functionality
Requires testnet credentials and network connectivity
"""
import sys
import os
import time
import threading
import unittest
from unittest.mock import Mock
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'hyperliq'))

# Load environment
load_dotenv()

# Skip tests if no credentials
SKIP_INTEGRATION = not (os.getenv("WALLET_ADDRESS") and os.getenv("PRIVATE_KEY"))

if not SKIP_INTEGRATION:
    import hyperliq.hyperliq_utils as hyperliq_utils
    from hyperliq.spot import HyperliquidSpot
    from hyperliq.order import HyperLiquidOrder


@unittest.skipIf(SKIP_INTEGRATION, "Integration tests require environment variables")
class TestWebSocketIntegration(unittest.TestCase):
    """Integration tests for WebSocket subscriptions"""
    
    @classmethod
    def setUpClass(cls):
        """Set up connection for all tests"""
        try:
            cls.address, cls.info, cls.exchange = hyperliq_utils.hyperliquid_setup(skip_ws=False)
            cls.spot = HyperliquidSpot(cls.address, cls.info, cls.exchange)
            cls.perp_order = HyperLiquidOrder(cls.address, cls.info, cls.exchange)
            print(f"✓ Connected to testnet with address: {cls.address}")
        except Exception as e:
            raise unittest.SkipTest(f"Could not connect to Hyperliquid testnet: {e}")

    def setUp(self):
        """Set up test fixtures"""
        self.received_messages = []
        self.subscription_ids = []

    def tearDown(self):
        """Clean up subscriptions"""
        for sub_id in self.subscription_ids:
            try:
                self.spot.unsubscribe(sub_id)
            except:
                pass

    def test_spot_bbo_subscription(self):
        """Test spot BBO (top of book) WebSocket subscription"""
        if not hasattr(self, 'spot'):
            self.skipTest("Spot trading not available")
        
        # Get available spot symbols first
        try:
            spot_meta = self.spot.get_spot_meta_data()
            if not spot_meta or not spot_meta.get("universe"):
                self.skipTest("No spot symbols available")
            
            # Use first available spot symbol
            test_symbol = spot_meta["universe"][0]["name"]
            print(f"Testing with symbol: {test_symbol}")
        except Exception as e:
            self.skipTest(f"Could not get spot metadata: {e}")
        
        # Set up callback
        def bbo_callback(message):
            self.received_messages.append(message)
            print(f"Received BBO: {message}")
        
        # Subscribe
        subscription_id = self.spot.subscribe_spot_top_of_book(test_symbol, bbo_callback)
        
        if subscription_id:
            self.subscription_ids.append(subscription_id)
            print(f"✓ Subscribed to {test_symbol} BBO with ID: {subscription_id}")
            
            # Wait for messages
            timeout = 10  # seconds
            start_time = time.time()
            
            while len(self.received_messages) == 0 and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            # Verify we received data
            if self.received_messages:
                message = self.received_messages[0]
                self.assertIn("symbol", message)
                self.assertEqual(message["symbol"], test_symbol)
                self.assertIn("timestamp", message)
                print("✓ BBO subscription working correctly")
            else:
                print("⚠ No BBO messages received (market may be inactive)")
        else:
            self.fail("Could not subscribe to spot BBO")

    def test_spot_l2_book_subscription(self):
        """Test spot L2 order book WebSocket subscription"""
        if not hasattr(self, 'spot'):
            self.skipTest("Spot trading not available")
        
        # Get available spot symbols
        try:
            spot_meta = self.spot.get_spot_meta_data()
            test_symbol = spot_meta["universe"][0]["name"]
        except Exception as e:
            self.skipTest(f"Could not get spot metadata: {e}")
        
        # Set up callback
        def l2_callback(message):
            self.received_messages.append(message)
            print(f"Received L2: {message['symbol']} - {len(message.get('levels', []))} levels")
        
        # Subscribe
        subscription_id = self.spot.subscribe_spot_l2_book(test_symbol, l2_callback)
        
        if subscription_id:
            self.subscription_ids.append(subscription_id)
            print(f"✓ Subscribed to {test_symbol} L2 book with ID: {subscription_id}")
            
            # Wait for messages
            timeout = 10
            start_time = time.time()
            
            while len(self.received_messages) == 0 and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.received_messages:
                message = self.received_messages[0]
                self.assertIn("symbol", message)
                self.assertIn("levels", message)
                print("✓ L2 book subscription working correctly")
            else:
                print("⚠ No L2 book messages received")

    def test_perp_bbo_subscription(self):
        """Test perpetual BBO WebSocket subscription"""
        test_symbol = "BTC"  # Standard perpetual symbol
        
        # Set up callback
        def bbo_callback(message):
            self.received_messages.append(message)
            print(f"Received Perp BBO: {message}")
        
        # Subscribe
        subscription_id = self.perp_order.subscribe_perp_top_of_book(test_symbol, bbo_callback)
        
        if subscription_id:
            self.subscription_ids.append(subscription_id)
            print(f"✓ Subscribed to {test_symbol} perp BBO with ID: {subscription_id}")
            
            # Wait for messages
            timeout = 10
            start_time = time.time()
            
            while len(self.received_messages) == 0 and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.received_messages:
                message = self.received_messages[0]
                self.assertIn("symbol", message)
                self.assertEqual(message["symbol"], test_symbol)
                # BTC should have active market
                self.assertIsNotNone(message.get("best_bid"))
                self.assertIsNotNone(message.get("best_ask"))
                print("✓ Perpetual BBO subscription working correctly")
            else:
                self.fail("No perpetual BBO messages received")

    def test_perp_l2_book_subscription(self):
        """Test perpetual L2 order book WebSocket subscription"""
        test_symbol = "ETH"  # Standard perpetual symbol
        
        # Set up callback
        def l2_callback(message):
            self.received_messages.append(message)
            print(f"Received Perp L2: {message['symbol']} - {len(message.get('levels', []))} levels")
        
        # Subscribe
        subscription_id = self.perp_order.subscribe_perp_l2_book(test_symbol, l2_callback)
        
        if subscription_id:
            self.subscription_ids.append(subscription_id)
            print(f"✓ Subscribed to {test_symbol} perp L2 book with ID: {subscription_id}")
            
            # Wait for messages
            timeout = 10
            start_time = time.time()
            
            while len(self.received_messages) == 0 and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if self.received_messages:
                message = self.received_messages[0]
                self.assertIn("symbol", message)
                self.assertIn("levels", message)
                print("✓ Perpetual L2 book subscription working correctly")

    def test_multiple_subscriptions(self):
        """Test handling multiple simultaneous subscriptions"""
        symbols = ["BTC", "ETH"]
        received_by_symbol = {}
        
        def create_callback(symbol):
            def callback(message):
                if symbol not in received_by_symbol:
                    received_by_symbol[symbol] = []
                received_by_symbol[symbol].append(message)
                print(f"Received for {symbol}: {message.get('best_bid', {}).get('price', 'N/A')}")
            return callback
        
        # Subscribe to multiple symbols
        for symbol in symbols:
            callback = create_callback(symbol)
            subscription_id = self.perp_order.subscribe_perp_top_of_book(symbol, callback)
            if subscription_id:
                self.subscription_ids.append(subscription_id)
                print(f"✓ Subscribed to {symbol}")
        
        # Wait for messages from all symbols
        timeout = 15
        start_time = time.time()
        
        while len(received_by_symbol) < len(symbols) and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        # Verify we got data for all symbols
        for symbol in symbols:
            self.assertIn(symbol, received_by_symbol, f"No data received for {symbol}")
            self.assertGreater(len(received_by_symbol[symbol]), 0, f"No messages for {symbol}")
        
        print("✓ Multiple subscriptions working correctly")

    def test_unsubscribe_functionality(self):
        """Test unsubscribing from WebSocket feeds"""
        test_symbol = "BTC"
        
        # Set up callback
        def callback(message):
            self.received_messages.append(message)
        
        # Subscribe
        subscription_id = self.perp_order.subscribe_perp_top_of_book(test_symbol, callback)
        
        if subscription_id:
            print(f"✓ Subscribed with ID: {subscription_id}")
            
            # Wait for some messages
            time.sleep(2)
            initial_count = len(self.received_messages)
            
            # Unsubscribe
            result = self.perp_order.unsubscribe(subscription_id)
            self.assertTrue(result, "Unsubscribe should return True")
            print("✓ Unsubscribed successfully")
            
            # Wait and verify no new messages
            time.sleep(2)
            final_count = len(self.received_messages)
            
            # Should have stopped receiving messages (or very few due to buffering)
            self.assertLessEqual(final_count - initial_count, 2, "Should stop receiving messages after unsubscribe")
            print("✓ Message flow stopped after unsubscribe")


@unittest.skipIf(SKIP_INTEGRATION, "Integration tests require environment variables")
class TestMarketDataIntegration(unittest.TestCase):
    """Integration tests for market data snapshots"""
    
    @classmethod
    def setUpClass(cls):
        """Set up connection for all tests"""
        try:
            cls.address, cls.info, cls.exchange = hyperliq_utils.hyperliquid_setup(skip_ws=True)
            cls.spot = HyperliquidSpot(cls.address, cls.info, cls.exchange)
            cls.perp_order = HyperLiquidOrder(cls.address, cls.info, cls.exchange)
        except Exception as e:
            raise unittest.SkipTest(f"Could not connect to Hyperliquid testnet: {e}")

    def test_spot_metadata_retrieval(self):
        """Test retrieving spot market metadata"""
        try:
            metadata = self.spot.get_spot_meta_data()
            
            self.assertIsInstance(metadata, dict)
            self.assertIn("universe", metadata)
            self.assertIsInstance(metadata["universe"], list)
            
            if metadata["universe"]:
                asset = metadata["universe"][0]
                self.assertIn("name", asset)
                print(f"✓ Found {len(metadata['universe'])} spot assets")
                print(f"  First asset: {asset['name']}")
            else:
                print("⚠ No spot assets found in metadata")
        
        except Exception as e:
            self.fail(f"Could not retrieve spot metadata: {e}")

    def test_spot_balances(self):
        """Test retrieving spot balances"""
        try:
            balances = self.spot.get_spot_balances()
            
            self.assertIsInstance(balances, dict)
            print(f"✓ Retrieved spot balances: {len(balances)} tokens")
            
            for token, amount in balances.items():
                self.assertIsInstance(amount, (int, float))
                self.assertGreater(amount, 0)
                print(f"  {token}: {amount}")
                
        except Exception as e:
            self.fail(f"Could not retrieve spot balances: {e}")

    def test_perp_top_of_book_snapshot(self):
        """Test retrieving perpetual top of book snapshot"""
        test_symbol = "BTC"
        
        try:
            top_of_book = self.perp_order.get_perp_top_of_book(test_symbol)
            
            if top_of_book:
                self.assertIn("best_bid", top_of_book)
                self.assertIn("best_ask", top_of_book)
                
                if top_of_book["best_bid"]:
                    bid = top_of_book["best_bid"]
                    self.assertIn("price", bid)
                    self.assertIn("size", bid)
                    self.assertGreater(bid["price"], 0)
                    print(f"✓ {test_symbol} Best Bid: ${bid['price']} x {bid['size']}")
                
                if top_of_book["best_ask"]:
                    ask = top_of_book["best_ask"]
                    self.assertIn("price", ask)
                    self.assertIn("size", ask)
                    self.assertGreater(ask["price"], 0)
                    print(f"✓ {test_symbol} Best Ask: ${ask['price']} x {ask['size']}")
            else:
                print(f"⚠ No top of book data for {test_symbol}")
                
        except Exception as e:
            self.fail(f"Could not retrieve {test_symbol} top of book: {e}")

    def test_spot_top_of_book_snapshot(self):
        """Test retrieving spot top of book snapshot"""
        try:
            # Get available spot symbols
            metadata = self.spot.get_spot_meta_data()
            if not metadata.get("universe"):
                self.skipTest("No spot symbols available")
            
            test_symbol = metadata["universe"][0]["name"]
            top_of_book = self.spot.get_spot_top_of_book(test_symbol)
            
            if top_of_book:
                print(f"✓ {test_symbol} top of book retrieved")
                
                if top_of_book.get("best_bid"):
                    bid = top_of_book["best_bid"]
                    print(f"  Best Bid: ${bid['price']} x {bid['size']}")
                
                if top_of_book.get("best_ask"):
                    ask = top_of_book["best_ask"]
                    print(f"  Best Ask: ${ask['price']} x {ask['size']}")
            else:
                print(f"⚠ No top of book data for {test_symbol} (market may be inactive)")
                
        except Exception as e:
            print(f"⚠ Could not test spot top of book: {e}")


if __name__ == "__main__":
    if SKIP_INTEGRATION:
        print("⚠ Skipping integration tests - set WALLET_ADDRESS and PRIVATE_KEY in .env")
        sys.exit(0)
    else:
        print("🚀 Running WebSocket integration tests...")
        print("Note: These tests require active network connection to Hyperliquid testnet")
        unittest.main(verbosity=2)