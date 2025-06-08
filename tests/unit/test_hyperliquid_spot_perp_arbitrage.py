import unittest
from unittest.mock import patch, Mock, MagicMock
import time
import logging
import sys
import os
import math # Import math

# Adjust path to import from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from strategies.hyperliquid_spot_perp_arbitrage import SignalCalculator, SpotPerpArbitrageBot, execute_twap_order

# Disable all logging for tests to keep output clean
logging.disable(logging.CRITICAL)

class TestSignalCalculator(unittest.TestCase):
    def setUp(self):
        self.mock_api_client = Mock()
        self.signal_calculator = SignalCalculator(self.mock_api_client)
        # Base mock data, can be overridden in tests
        self.signal_calculator.mock_data_store = {
            "ETH": {"spot_price": 3000.0, "perp_price": 3003.0, "next_funding_rate_hourly": 0.01,
                    "spot_order_book": {"bids": [[2999,100]], "asks": [[3001,100]]},
                    "perp_order_book": {"bids": [[3000,150]], "asks": [[3002,150]]}},
            "BTC": {"spot_price": 60000.0, "perp_price": 60030.0, "next_funding_rate_hourly": 0.005,
                    "spot_order_book": {"bids": [[59990,10]], "asks": [[60020,10]]},
                    "perp_order_book": {"bids": [[60000,15]], "asks": [[60030,15]]}},
        }
        self.trade_amount_usd = 1000.0

    def test_calculate_opportunity_score_sufficient_liquidity(self):
        market_data = self.signal_calculator.fetch_market_data("ETH")
        # ETH example: funding 0.01, basis ((3003-3000)/3000)*100 = 0.1%. Fees 0.2%.
        # Score = 0.01 + 0.1 - 0.2 = -0.09
        expected_score = 0.01 + 0.1 - self.signal_calculator.ROUND_TRIP_FEES_PERCENT
        expected_basis_percent = 0.1

        with patch.object(self.signal_calculator, '_check_liquidity', return_value=True) as mock_check_liq:
            score, basis_percent = self.signal_calculator.calculate_opportunity_score(market_data, self.trade_amount_usd)
            self.assertAlmostEqual(score, expected_score)
            self.assertAlmostEqual(basis_percent, expected_basis_percent)
            self.assertEqual(mock_check_liq.call_count, 2) # Spot and Perp

    def test_calculate_opportunity_score_insufficient_liquidity(self):
        market_data = self.signal_calculator.fetch_market_data("ETH")
        with patch.object(self.signal_calculator, '_check_liquidity', return_value=False):
            score, basis_percent = self.signal_calculator.calculate_opportunity_score(market_data, self.trade_amount_usd)
            self.assertIsNone(score)
            self.assertIsNone(basis_percent)

    def test_check_liquidity_sufficient(self):
        # Price = 100. Ask check: p <= 100 * (1+0.005) = 100.5. Bid check: p >= 100 * (1-0.005) = 99.5
        order_book = {"bids": [[100, 10]], "asks": [[100.4, 10]]} # Ask price 100.4 is within slippage
        # Trade amount 500 USD at price 100 means 5 units needed. Both sides have 10 units.
        self.assertTrue(self.signal_calculator._check_liquidity(order_book, 500, 100))

    def test_check_liquidity_insufficient_ask(self):
        # Price = 100. Ask check: p <= 100.5. Order book ask [101, 4] -> 101 is not <= 100.5, so ask_volume = 0
        # This test is correct as it is, it should be False.
        # However, to make it more explicit that it's due to volume AFTER slippage:
        order_book = {"bids": [[100, 10]], "asks": [[100.4, 4]]} # Ask price 100.4 is within slippage, but only 4 units
        self.assertFalse(self.signal_calculator._check_liquidity(order_book, 500, 100)) # Needs 5 units

    def test_check_liquidity_insufficient_bid(self):
        # Price = 100. Bid check: p >= 99.5. Order book bid [99, 4] -> 99 is not >= 99.5, so bid_volume = 0.
        # To make it more explicit that it's due to volume AFTER slippage:
        order_book = {"bids": [[99.6, 4]], "asks": [[100.4, 10]]} # Bid price 99.6 is within slippage, but only 4 units
        self.assertFalse(self.signal_calculator._check_liquidity(order_book, 500, 100)) # Needs 5 units

    def test_find_best_opportunity(self):
        # ETH score: -0.09
        # BTC score: funding 0.005, basis ((60030-60000)/60000)*100 = 0.05%. Fees 0.2%.
        # Score = 0.005 + 0.05 - 0.2 = -0.145
        # So ETH should be better here.
        with patch.object(self.signal_calculator, '_check_liquidity', return_value=True):
            best_asset, best_score, _, best_basis = self.signal_calculator.find_best_opportunity(["ETH", "BTC"], self.trade_amount_usd)
            self.assertEqual(best_asset, "ETH")
            self.assertAlmostEqual(best_score, -0.09)
            self.assertAlmostEqual(best_basis, 0.1)

    def test_find_best_opportunity_no_good_options(self):
        with patch.object(self.signal_calculator, 'calculate_opportunity_score', return_value=(None, None)):
            best_asset, best_score, _, _ = self.signal_calculator.find_best_opportunity(["ETH", "BTC"], self.trade_amount_usd)
            self.assertIsNone(best_asset)
            self.assertEqual(best_score, -math.inf)


class TestSpotPerpArbitrageBot(unittest.TestCase):
    def setUp(self):
        self.mock_signal_calculator = MagicMock(spec=SignalCalculator)
        self.mock_api_client = Mock()

        self.bot_params = {
            "assets_to_monitor": ["ETH", "BTC"],
            "trade_amount_usd": 1000.0,
            "entry_threshold": 0.05,
            "rotation_threshold": 0.02,
            "position_decay_threshold": 0.01,
            "min_holding_period_seconds": 60,
            "twap_duration_minutes": 1,
            "twap_num_intervals": 2,
            "stop_loss_basis_threshold_percentage": 1.0
        }
        self.bot = SpotPerpArbitrageBot(self.mock_signal_calculator, self.mock_api_client, **self.bot_params)

    def test_initial_state(self):
        self.assertEqual(self.bot.current_state, "SEARCHING")
        self.assertIsNone(self.bot.current_position)

    @patch('strategies.hyperliquid_spot_perp_arbitrage.execute_twap_order', return_value=True)
    @patch('time.time', return_value=12345.0)
    def test_searching_to_position_open(self, mock_time, mock_execute_twap):
        mock_market_data = {"spot_price": 3000, "perp_price": 3003, "next_funding_rate_hourly": 0.1} # Ensure these keys exist
        entry_score = 0.1 # Above threshold 0.05
        entry_basis = 0.1
        self.mock_signal_calculator.find_best_opportunity.return_value = ("ETH", entry_score, mock_market_data, entry_basis)

        self.bot.run_cycle()

        self.assertEqual(self.bot.current_state, "POSITION_OPEN")
        self.assertIsNotNone(self.bot.current_position)
        self.assertEqual(self.bot.current_position["asset_symbol"], "ETH")
        self.assertEqual(self.bot.current_position["entry_score"], entry_score)
        self.assertEqual(self.bot.current_position["entry_basis_percentage"], entry_basis)
        self.assertEqual(self.bot.entry_timestamp, 12345.0)
        mock_execute_twap.assert_called_once_with(
            self.mock_api_client, "ETH", "ENTRY", self.bot_params["trade_amount_usd"],
            self.bot_params["twap_duration_minutes"], self.bot_params["twap_num_intervals"]
        )

    @patch('strategies.hyperliquid_spot_perp_arbitrage.execute_twap_order') # Mock TWAP for exit
    @patch('time.time')
    def test_minimum_holding_period(self, mock_time, mock_execute_twap_exit):
        # Setup bot in POSITION_OPEN state
        entry_time = 12345.0
        mock_time.return_value = entry_time # For entry
        self.bot.entry_timestamp = entry_time
        self.bot.current_state = "POSITION_OPEN"
        self.bot.current_position = {"asset_symbol": "ETH", "entry_spot_price": 3000, "entry_perp_price": 3003, "entry_basis_percentage": 0.1, "entry_score": 0.1, "market_data_at_entry":{}}

        # Simulate time is still within min_holding_period
        mock_time.return_value = entry_time + self.bot_params["min_holding_period_seconds"] - 10

        # Conditions that would normally cause exit (decay)
        mock_market_data_decay = {"spot_price": 3000, "perp_price": 3000, "next_funding_rate_hourly": 0.001} # Low score
        self.mock_signal_calculator.fetch_market_data.return_value = mock_market_data_decay
        self.mock_signal_calculator.calculate_opportunity_score.return_value = (0.005, 0.0) # Score below decay_threshold

        self.bot.run_cycle()

        self.assertEqual(self.bot.current_state, "POSITION_OPEN") # Should still be open
        mock_execute_twap_exit.assert_not_called()


    @patch('strategies.hyperliquid_spot_perp_arbitrage.execute_twap_order', return_value=True)
    @patch('time.time')
    def test_decay_exit(self, mock_time, mock_execute_twap_exit):
        entry_time = 10000.0
        mock_time.return_value = entry_time # For entry
        self.bot.entry_timestamp = entry_time
        self.bot.current_state = "POSITION_OPEN"
        self.bot.current_position = {"asset_symbol": "ETH", "entry_spot_price": 3000, "entry_perp_price": 3003, "entry_basis_percentage": 0.1, "entry_score": 0.1, "market_data_at_entry":{}}

        # Simulate time has passed min_holding_period
        mock_time.return_value = entry_time + self.bot_params["min_holding_period_seconds"] + 10

        # Current position score drops below decay threshold
        mock_market_data_decayed = {"spot_price": 3000, "perp_price": 3000, "next_funding_rate_hourly": 0.001}
        self.mock_signal_calculator.fetch_market_data.return_value = mock_market_data_decayed
        # Score (e.g. -0.1) < decay_threshold (0.01)
        self.mock_signal_calculator.calculate_opportunity_score.return_value = (-0.1, 0.0)
        # No better alternative
        self.mock_signal_calculator.find_best_opportunity.return_value = (None, -math.inf, None, None)

        self.bot.run_cycle()

        self.assertEqual(self.bot.current_state, "SEARCHING")
        mock_execute_twap_exit.assert_called_once_with(
            self.mock_api_client, "ETH", "EXIT", self.bot_params["trade_amount_usd"],
            self.bot_params["twap_duration_minutes"], self.bot_params["twap_num_intervals"]
        )
        self.assertIsNone(self.bot.current_position)

    @patch('strategies.hyperliquid_spot_perp_arbitrage.execute_twap_order', return_value=True) # Mocks both exit and entry parts of rotation
    @patch('time.time')
    def test_rotation_exit(self, mock_time, mock_execute_twap_rotation):
        entry_time = 10000.0
        current_sim_time = entry_time + self.bot_params["min_holding_period_seconds"] + 10

        mock_time.return_value = current_sim_time # For current cycle
        self.bot.entry_timestamp = entry_time # Original entry time
        self.bot.current_state = "POSITION_OPEN"
        eth_market_data = {"spot_price": 3000, "perp_price": 3001, "next_funding_rate_hourly": 0.05}
        self.bot.current_position = {"asset_symbol": "ETH", "entry_spot_price": 3000, "entry_perp_price": 3001, "entry_basis_percentage": (1/3000)*100, "entry_score": 0.05, "market_data_at_entry": eth_market_data}

        # Current ETH score (refreshed)
        current_eth_score = 0.05 # Example current score
        current_eth_basis = (1/3000)*100
        self.mock_signal_calculator.fetch_market_data.return_value = eth_market_data # For ETH refresh
        self.mock_signal_calculator.calculate_opportunity_score.return_value = (current_eth_score, current_eth_basis)

        # BTC becomes a much better opportunity
        btc_market_data = {"spot_price": 60000, "perp_price": 60120, "next_funding_rate_hourly": 0.1} # Basis 0.2%, Funding 0.1%
        # Score_BTC = 0.1 + 0.2 - 0.2(fees) = 0.1
        # Rotation if Score_BTC > current_eth_score + rotation_threshold (0.02)
        # 0.1 > 0.05 + 0.02  (0.1 > 0.07) -> True
        best_alt_score = 0.1
        best_alt_basis = 0.2
        self.mock_signal_calculator.find_best_opportunity.return_value = ("BTC", best_alt_score, btc_market_data, best_alt_basis)

        self.bot.run_cycle()

        self.assertEqual(self.bot.current_state, "POSITION_OPEN")
        self.assertEqual(self.bot.current_position["asset_symbol"], "BTC")
        self.assertEqual(self.bot.current_position["entry_score"], best_alt_score)
        self.assertEqual(self.bot.entry_timestamp, current_sim_time) # Timestamp reset to now
        # Check execute_twap_order calls: one for exiting ETH, one for entering BTC
        self.assertEqual(mock_execute_twap_rotation.call_count, 2)
        mock_execute_twap_rotation.assert_any_call(self.mock_api_client, "ETH", "EXIT", self.bot.trade_amount_usd, self.bot.twap_duration_minutes, self.bot.twap_num_intervals)
        mock_execute_twap_rotation.assert_any_call(self.mock_api_client, "BTC", "ENTRY", self.bot.trade_amount_usd, self.bot.twap_duration_minutes, self.bot.twap_num_intervals)


    @patch.object(SpotPerpArbitrageBot, '_execute_immediate_exit_trade', return_value=True)
    @patch('time.time')
    def test_stop_loss_trigger(self, mock_time, mock_immediate_exit):
        entry_time = 10000.0
        mock_time.return_value = entry_time # For entry timestamp
        self.bot.entry_timestamp = entry_time
        self.bot.current_state = "POSITION_OPEN"
        # Entry: Spot 3000, Perp 3003. Basis Value = 3.
        self.bot.current_position = {
            "asset_symbol": "ETH",
            "entry_spot_price": 3000.0,
            "entry_perp_price": 3003.0,
            "entry_basis_percentage": 0.1, # (3/3000)*100
            "entry_score": 0.1,
            "market_data_at_entry": {}
        }

        # Current market data that triggers stop-loss
        # Entry basis value = 3.0. Stop loss threshold 1.0% of entry spot price (3000 * 0.01 = 30)
        # Basis change = current_basis_value - entry_basis_value
        # If current_basis_value - 3.0 > 30  => current_basis_value > 33
        # e.g. spot = 3000, perp = 3034 => current_basis_value = 34
        stop_loss_market_data = {"spot_price": 3000.0, "perp_price": 3034.0, "next_funding_rate_hourly": 0.01}
        self.mock_signal_calculator.fetch_market_data.return_value = stop_loss_market_data

        # Simulate time hasn't moved much, stop loss is checked before min holding period
        mock_time.return_value = entry_time + 5

        self.bot.run_cycle()

        self.assertEqual(self.bot.current_state, "SEARCHING")
        mock_immediate_exit.assert_called_once_with("ETH", "StopLossHit")
        self.assertIsNone(self.bot.current_position)


if __name__ == '__main__':
    unittest.main()
