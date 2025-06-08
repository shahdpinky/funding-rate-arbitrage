# Hyperliquid Spot-Perp Arbitrage Bot
import math
import time
import random
import logging # Added logging

# --- Module Level Logger ---
# Logger will be configured in if __name__ == '__main__' or by the application using this module
logger = logging.getLogger(__name__)

# --- TWAP Execution Helper ---
def execute_twap_order(api_client, asset_symbol: str, order_type: str,
                       total_amount_usd: float, duration_minutes: int, num_intervals: int) -> bool:
    if num_intervals <= 0 or duration_minutes <= 0:
        logger.error(f"TWAP: Error - Invalid TWAP params (duration: {duration_minutes}, intervals: {num_intervals}).")
        return False

    interval_delay_seconds = (duration_minutes * 60) / num_intervals
    amount_per_interval_usd = total_amount_usd / num_intervals
    asset_symbol_spot = asset_symbol
    asset_symbol_perp = asset_symbol

    logger.info(f"TWAP: Starting {order_type} for {asset_symbol} over {duration_minutes} mins, {num_intervals} intervals.")
    logger.info(f"TWAP: Total: ${total_amount_usd:.2f}, Per Interval: ${amount_per_interval_usd:.2f}, Delay: {interval_delay_seconds:.2f}s")

    for i in range(num_intervals):
        logger.info(f"TWAP Interval {i+1}/{num_intervals} for {asset_symbol}:")
        if order_type == "ENTRY":
            logger.info(f"  Action: Buy ${amount_per_interval_usd:.2f} of {asset_symbol_spot} (spot).")
            # api_client.place_order(asset=asset_symbol_spot, side="buy", size_usd=amount_per_interval_usd, type="market")
            logger.info(f"  Action: Sell ${amount_per_interval_usd:.2f} of {asset_symbol_perp} (perp).")
            # api_client.place_order(asset=asset_symbol_perp, side="sell", size_usd=amount_per_interval_usd, type="market")
        elif order_type == "EXIT":
            logger.info(f"  Action: Sell ${amount_per_interval_usd:.2f} of {asset_symbol_spot} (spot).")
            # api_client.place_order(asset=asset_symbol_spot, side="sell", size_usd=amount_per_interval_usd, type="market")
            logger.info(f"  Action: Buy ${amount_per_interval_usd:.2f} of {asset_symbol_perp} (perp).")
            # api_client.place_order(asset=asset_symbol_perp, side="buy", size_usd=amount_per_interval_usd, type="market")
        else:
            logger.error(f"TWAP: Error - Unknown order_type: {order_type}")
            return False
        if i < num_intervals - 1:
            logger.debug(f"  Waiting {interval_delay_seconds:.2f}s...") # Debug for less verbosity
            time.sleep(interval_delay_seconds)
    logger.info(f"TWAP: Execution for {asset_symbol} ({order_type}) completed.")
    return True


class SignalCalculator:
    def __init__(self, hyperliquid_api_client):
        self.hyperliquid_api_client = hyperliquid_api_client
        self.ROUND_TRIP_FEES_PERCENT = 0.2
        self.mock_data_store = {
            "ETH": {"spot_price": 3000.0, "perp_price": 3001.5, "next_funding_rate_hourly": 0.005, "spot_order_book": {"bids": [[2999,100]], "asks": [[3001,100]]}, "perp_order_book": {"bids": [[3000,150]], "asks": [[3002,150]]}},
            "BTC": {"spot_price": 60000.0, "perp_price": 60010.0, "next_funding_rate_hourly": 0.002, "spot_order_book": {"bids": [[59990,10]], "asks": [[60020,10]]}, "perp_order_book": {"bids": [[60000,15]], "asks": [[60030,15]]}},
            "SOL": {"spot_price": 140.0, "perp_price": 139.5, "next_funding_rate_hourly": -0.001, "spot_order_book": {"bids": [[139.8,500]], "asks": [[140.2,500]]}, "perp_order_book": {"bids": [[139.9,600]], "asks": [[140.3,600]]}},
        }

    def fetch_market_data(self, asset_symbol: str) -> dict | None:
        logger.debug(f"SignalCalculator: Attempting to fetch market data for {asset_symbol}...")
        if asset_symbol in self.mock_data_store:
            data = self.mock_data_store[asset_symbol].copy()
            data["asset_symbol"] = asset_symbol
            logger.debug(f"SignalCalculator: Fetched mock data for {asset_symbol}: Spot={data['spot_price']}, Perp={data['perp_price']}")
            return data
        logger.warning(f"SignalCalculator: No mock data found for {asset_symbol}")
        return None

    def _check_liquidity(self, order_book: dict, trade_amount_usd: float, price: float, slippage_tolerance: float = 0.005) -> bool:
        if not order_book or not order_book.get("bids") or not order_book.get("asks") or price == 0: return False
        trade_amount_asset = trade_amount_usd / price
        ask_vol = sum(vol for p, vol in order_book["asks"] if p <= price * (1 + slippage_tolerance))
        bid_vol = sum(vol for p, vol in order_book["bids"] if p >= price * (1 - slippage_tolerance))
        liquidity_ok = ask_vol >= trade_amount_asset and bid_vol >= trade_amount_asset
        if not liquidity_ok:
            logger.debug(f"SignalCalculator: Insufficient liquidity for {trade_amount_usd} USD ({trade_amount_asset:.4f} units). Ask depth: {ask_vol:.4f}, Bid depth: {bid_vol:.4f} for price {price}.")
        return liquidity_ok

    def calculate_opportunity_score(self, market_data: dict, trade_amount_usd: float) -> tuple[float | None, float | None]:
        if not market_data: return None, None
        spot_price = market_data["spot_price"]
        perp_price = market_data["perp_price"]

        if not self._check_liquidity(market_data["spot_order_book"], trade_amount_usd, spot_price) or \
           not self._check_liquidity(market_data["perp_order_book"], trade_amount_usd, perp_price):
            logger.debug(f"SignalCalculator: Liquidity check failed for {market_data['asset_symbol']} with trade amount {trade_amount_usd} USD for score calculation.")
            return None, None

        if spot_price == 0: return 0.0, 0.0

        basis_percent = ((perp_price - spot_price) / spot_price) * 100
        score = market_data["next_funding_rate_hourly"] + basis_percent - self.ROUND_TRIP_FEES_PERCENT
        logger.debug(f"SignalCalculator: Asset: {market_data['asset_symbol']}, Spot: {spot_price}, Perp: {perp_price}, Funding: {market_data['next_funding_rate_hourly']:.4f}%, Basis: {basis_percent:.4f}%, Fees: {self.ROUND_TRIP_FEES_PERCENT}%, Score: {score:.4f}")
        return score, basis_percent

    def find_best_opportunity(self, assets: list[str], trade_amount_usd: float, current_asset_symbol: str | None = None) -> tuple[str | None, float, dict | None, float | None]:
        best_asset, best_score, best_market_data, best_basis = None, -math.inf, None, None
        logger.debug(f"SignalCalculator: Finding best opportunity among {assets} (excluding {current_asset_symbol}).")
        for asset in assets:
            if asset == current_asset_symbol: continue
            md = self.fetch_market_data(asset)
            if not md: continue # Warning already logged by fetch_market_data
            score, basis = self.calculate_opportunity_score(md, trade_amount_usd)
            if score is not None and score > best_score:
                best_score, best_asset, best_market_data, best_basis = score, asset, md, basis
        if best_asset:
            logger.debug(f"SignalCalculator: Best opportunity found: {best_asset} (Score: {best_score:.4f}, Basis: {best_basis:.4f}%)")
        else:
            logger.debug(f"SignalCalculator: No suitable best opportunity found.")
        return best_asset, best_score, best_market_data, best_basis


class SpotPerpArbitrageBot:
    def __init__(self, signal_calculator: SignalCalculator, hyperliquid_api_client,
                 assets_to_monitor: list[str], trade_amount_usd: float,
                 entry_threshold: float, rotation_threshold: float,
                 position_decay_threshold: float, min_holding_period_seconds: int,
                 twap_duration_minutes: int, twap_num_intervals: int,
                 stop_loss_basis_threshold_percentage: float):
        self.signal_calculator = signal_calculator
        self.hyperliquid_api_client = hyperliquid_api_client
        self.current_state: str = "SEARCHING"
        self.current_position: dict | None = None
        self.entry_timestamp: float | None = None

        self.assets_to_monitor = assets_to_monitor
        self.trade_amount_usd = trade_amount_usd
        self.entry_threshold = entry_threshold
        self.rotation_threshold = rotation_threshold
        self.position_decay_threshold = position_decay_threshold
        self.min_holding_period_seconds = min_holding_period_seconds
        self.twap_duration_minutes = twap_duration_minutes
        self.twap_num_intervals = twap_num_intervals
        self.stop_loss_basis_threshold_percentage = stop_loss_basis_threshold_percentage

        logger.info("SpotPerpArbitrageBot initialized.")
        logger.info(f"Monitoring: {self.assets_to_monitor}, Trade Amount: ${self.trade_amount_usd}")
        logger.info(f"Entry Threshold: {self.entry_threshold}, Rotation Add: {self.rotation_threshold}, Decay Threshold: {self.position_decay_threshold}")
        logger.info(f"Min Holding: {self.min_holding_period_seconds}s, TWAP: {self.twap_duration_minutes}m/{self.twap_num_intervals} intervals")
        logger.info(f"Stop Loss Basis Threshold: {self.stop_loss_basis_threshold_percentage}%")


    def _execute_immediate_exit_trade(self, asset_symbol: str, reason: str) -> bool:
        logger.critical(f"CRITICAL: Executing IMMEDIATE EXIT for {asset_symbol} due to {reason}.")
        # TODO: Place IMMEDIATE market order to sell spot
        logger.info(f"  IMMEDIATE ACTION: Sell {self.trade_amount_usd} USD of {asset_symbol} (spot).")
        # TODO: Place IMMEDIATE market order to buy perp
        logger.info(f"  IMMEDIATE ACTION: Buy {self.trade_amount_usd} USD of {asset_symbol} (perp).")
        logger.info(f"Immediate exit for {asset_symbol} simulated as successful.")
        return True


    def _execute_entry_trade(self, asset_symbol: str, market_data_at_entry: dict, entry_score: float, entry_basis_percentage: float) -> bool:
        logger.info(f"BOT: Attempting ENTRY for {asset_symbol} (Score: {entry_score:.4f}, Basis: {entry_basis_percentage:.4f}%) via TWAP.")
        success = execute_twap_order(
            self.hyperliquid_api_client, asset_symbol, "ENTRY", self.trade_amount_usd,
            self.twap_duration_minutes, self.twap_num_intervals
        )
        if success:
            self.entry_timestamp = time.time()
            self.current_position = {
                "asset_symbol": asset_symbol,
                "entry_spot_price": market_data_at_entry["spot_price"],
                "entry_perp_price": market_data_at_entry["perp_price"],
                "entry_basis_percentage": entry_basis_percentage,
                "entry_score": entry_score, # Storing score at entry
                "market_data_at_entry": market_data_at_entry
            }
            logger.info(f"BOT: TWAP Entry for {asset_symbol} successful. Entry basis: {entry_basis_percentage:.4f}%.")
        else:
            logger.warning(f"BOT: TWAP Entry for {asset_symbol} failed.") # Warning as it's a trade failure
        return success

    def _execute_exit_trade(self, asset_symbol: str, reason: str) -> bool:
        logger.info(f"BOT: Attempting EXIT for {asset_symbol} via TWAP. Reason: {reason}.")
        success = execute_twap_order(
            self.hyperliquid_api_client, asset_symbol, "EXIT", self.trade_amount_usd,
            self.twap_duration_minutes, self.twap_num_intervals
        )
        if success:
            logger.info(f"BOT: TWAP Exit for {asset_symbol} successful.")
        else:
            logger.warning(f"BOT: TWAP Exit for {asset_symbol} failed.") # Warning
        return success

    def _execute_rotation_trade(self, old_asset_symbol: str, new_asset_symbol: str,
                               new_asset_market_data: dict, new_asset_score: float, new_asset_basis: float) -> bool:
        logger.info(f"BOT: Attempting ROTATION from {old_asset_symbol} to {new_asset_symbol} via TWAP.")
        logger.info(f"BOT: Rotating - Step 1: Exiting {old_asset_symbol}.")
        exit_success = self._execute_exit_trade(old_asset_symbol, "Rotation")

        if exit_success:
            logger.info(f"BOT: Rotating - Successfully exited {old_asset_symbol}.")
            logger.info(f"BOT: Rotating - Step 2: Entering {new_asset_symbol} (Score: {new_asset_score:.4f}, Basis: {new_asset_basis:.4f}%).")
            entry_success = self._execute_entry_trade(new_asset_symbol, new_asset_market_data, new_asset_score, new_asset_basis)
            if entry_success:
                logger.info(f"BOT: TWAP Rotation to {new_asset_symbol} successful.")
                return True
            else:
                logger.error(f"BOT: ERROR - Failed to TWAP enter {new_asset_symbol} during rotation after exiting {old_asset_symbol}.") # Error
                return False
        else:
            logger.warning(f"BOT: Rotation aborted - Failed to TWAP exit old position {old_asset_symbol}.") # Warning
            return False

    def _check_and_maintain_margin(self):
        if self.current_position:
            logger.debug(f"BOT: # TODO: Implement margin check for {self.current_position['asset_symbol']}-PERP.")
            pass

    def run_cycle(self):
        logger.info(f"--- BOT Cycle --- State: {self.current_state}, Position: {self.current_position['asset_symbol'] if self.current_position else 'None'} ---")
        current_time = time.time()
        self._check_and_maintain_margin()

        if self.current_state == "SEARCHING":
            best_asset, best_score, best_md, best_basis = self.signal_calculator.find_best_opportunity(
                self.assets_to_monitor, self.trade_amount_usd
            )
            logger.info(f"BOT: Searching. Best: {best_asset} (Score: {best_score if best_score != -math.inf else 'N/A'}, Basis: {best_basis if best_basis is not None else 'N/A'}%)")
            if best_asset and best_md and best_score is not None and best_basis is not None and best_score > self.entry_threshold:
                logger.info(f"BOT: Opportunity {best_asset} (Score: {best_score:.4f}, Basis: {best_basis:.4f}%) meets entry threshold ({self.entry_threshold}).")
                if self._execute_entry_trade(best_asset, best_md, best_score, best_basis):
                    self.current_state = "POSITION_OPEN"
                    logger.info(f"BOT: New state: {self.current_state}, Position: {self.current_position['asset_symbol']}")
            else:
                logger.info(f"BOT: No suitable opportunity found or best score below entry threshold.")

        elif self.current_state == "POSITION_OPEN":
            if not self.current_position or not self.entry_timestamp:
                logger.error("BOT: ERROR - In POSITION_OPEN state without position/timestamp. Resetting.")
                self.current_state = "SEARCHING"; self.current_position = None; self.entry_timestamp = None; return

            pos_asset = self.current_position["asset_symbol"]
            fresh_md_current_pos = self.signal_calculator.fetch_market_data(pos_asset)

            if not fresh_md_current_pos:
                logger.critical(f"BOT: CRITICAL - Data fetch failed for current position {pos_asset}. Executing immediate exit.")
                if self._execute_immediate_exit_trade(pos_asset, "Critical data fetch error"):
                    self.current_state = "SEARCHING"; self.current_position = None; self.entry_timestamp = None
                return

            current_spot_price = fresh_md_current_pos["spot_price"]
            current_perp_price = fresh_md_current_pos["perp_price"]
            entry_spot_price = self.current_position["entry_spot_price"]
            entry_perp_price = self.current_position["entry_perp_price"]
            entry_basis_value = entry_perp_price - entry_spot_price
            current_basis_value = current_perp_price - current_spot_price
            basis_change_usd = current_basis_value - entry_basis_value
            basis_change_percentage = (basis_change_usd / entry_spot_price) * 100 if entry_spot_price != 0 else 0

            logger.info(f"BOT: Stop-Loss Check for {pos_asset}: Entry BasisVal: {entry_basis_value:.2f}, Curr BasisVal: {current_basis_value:.2f}. Change: {basis_change_percentage:.4f}%. Threshold: {self.stop_loss_basis_threshold_percentage}%.")

            if basis_change_percentage > self.stop_loss_basis_threshold_percentage: # Assuming widening basis is loss
                logger.warning(f"BOT: STOP-LOSS TRIGGERED for {pos_asset}! Basis change {basis_change_percentage:.4f}% > threshold {self.stop_loss_basis_threshold_percentage}%.")
                if self._execute_immediate_exit_trade(pos_asset, "StopLossHit"):
                    self.current_state = "SEARCHING"; self.current_position = None; self.entry_timestamp = None
                return

            time_in_position = current_time - self.entry_timestamp
            if time_in_position < self.min_holding_period_seconds:
                logger.info(f"BOT: {pos_asset} in min holding period ({time_in_position:.0f}s < {self.min_holding_period_seconds}s). Holding."); return

            logger.info(f"BOT: {pos_asset} min holding period passed.")
            current_score, current_basis = self.signal_calculator.calculate_opportunity_score(fresh_md_current_pos, self.trade_amount_usd)

            if current_score is None:
                logger.warning(f"BOT: {pos_asset} liquidity dried up post-entry. Exiting via TWAP.")
                if self._execute_exit_trade(pos_asset, "Liquidity dried up"):
                    self.current_state = "SEARCHING"; self.current_position = None; self.entry_timestamp = None
                return

            logger.info(f"BOT: Refreshed score for {pos_asset}: {current_score:.4f} (Basis: {current_basis:.4f}%)")
            self.current_position["current_score_of_position"] = current_score # Store refreshed score

            alt_asset, alt_score, alt_md, alt_basis = self.signal_calculator.find_best_opportunity(
                self.assets_to_monitor, self.trade_amount_usd, pos_asset
            )
            if alt_asset and alt_md and alt_score is not None and alt_basis is not None and \
               alt_score > current_score + self.rotation_threshold:
                logger.info(f"BOT: Alternative {alt_asset} (Score: {alt_score:.4f}) better than {pos_asset} (Curr Score: {current_score:.4f}, Rot Threshold: {self.rotation_threshold}). Rotating.")
                if self._execute_rotation_trade(pos_asset, alt_asset, alt_md, alt_score, alt_basis):
                    logger.info(f"BOT: Successfully rotated to {alt_asset}.")
                else:
                    logger.warning(f"BOT: Rotation failed. Holding {pos_asset}.") # Warning
                return

            if current_score < self.position_decay_threshold:
                logger.info(f"BOT: {pos_asset} score ({current_score:.4f}) below decay threshold ({self.position_decay_threshold}). Exiting via TWAP.")
                if self._execute_exit_trade(pos_asset, "Position decayed"):
                    self.current_state = "SEARCHING"; self.current_position = None; self.entry_timestamp = None
            else:
                logger.info(f"BOT: Position {pos_asset} score ({current_score:.4f}) is acceptable. Holding.")


if __name__ == '__main__':
    # --- Basic Logger Configuration ---
    logging.basicConfig(level=logging.INFO, # Change to DEBUG for more verbose SignalCalculator output
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')

    # If you want to specifically set the level for this module's logger if it was set differently by root config
    # logging.getLogger(__name__).setLevel(logging.DEBUG)

    class MockHyperliquidAPIClient:
        def place_order(self, asset, side, size_usd, type, tif=None):
            logger.info(f"  MockAPI: Place {type} order: {asset}, {side}, ${size_usd:.2f}" + (f" TIF:{tif}" if tif else ""))
            return {"status": "ok", "order_id": random.randint(1000,9999)}
        def add_margin(self, asset_symbol_perp, amount):
            logger.info(f"  MockAPI: Adding ${amount} margin to {asset_symbol_perp}.")
            return {"status": "ok"}

    hl_client = MockHyperliquidAPIClient()
    signal_calc = SignalCalculator(hyperliquid_api_client=hl_client)

    bot_config = {
        "assets_to_monitor": ["ETH", "BTC"],
        "trade_amount_usd": 1000.0,
        "entry_threshold": 0.05,
        "rotation_threshold": 0.02,
        "position_decay_threshold": 0.01,
        "min_holding_period_seconds": 1,
        "twap_duration_minutes": 0.02,
        "twap_num_intervals": 2,
        "stop_loss_basis_threshold_percentage": 1.0
    }

    arbitrage_bot = SpotPerpArbitrageBot(signal_calc, hl_client, **bot_config)

    logger.info("\n\n===== BOT SIMULATION WITH LOGGING START =====")

    # Cycle 1: ETH entry
    logger.info("\n--- SIM: Cycle 1 - ETH Entry ---")
    signal_calc.mock_data_store["ETH"]["spot_price"] = 3000.0
    signal_calc.mock_data_store["ETH"]["perp_price"] = 3003.0
    signal_calc.mock_data_store["ETH"]["next_funding_rate_hourly"] = 0.20
    arbitrage_bot.run_cycle()

    # Cycle 2: Simulate time passing for min hold, then trigger stop-loss
    if arbitrage_bot.current_state == "POSITION_OPEN":
        logger.info(f"\n--- SIM: Cycle 2 - Trigger Stop-Loss for ETH ---")
        arbitrage_bot.entry_timestamp -= (bot_config["min_holding_period_seconds"] + 2) # Ensure time has passed

        signal_calc.mock_data_store["ETH"]["spot_price"] = 3000.0
        signal_calc.mock_data_store["ETH"]["perp_price"] = 3034.0 # Basis widens from 3 to 34. (34-3)/3000*100 = 1.033% change. Threshold 1.0%
        logger.info(f"SIM: Manipulated ETH data for Stop-Loss: Spot={signal_calc.mock_data_store['ETH']['spot_price']}, Perp={signal_calc.mock_data_store['ETH']['perp_price']}")
        arbitrage_bot.run_cycle()

    # Cycle 3: Searching again
    logger.info("\n--- SIM: Cycle 3 - Searching again ---")
    if arbitrage_bot.current_state == "SEARCHING":
        signal_calc.mock_data_store["BTC"]["spot_price"] = 60000.0
        signal_calc.mock_data_store["BTC"]["perp_price"] = 60060.0
        signal_calc.mock_data_store["BTC"]["next_funding_rate_hourly"] = 0.20
        arbitrage_bot.run_cycle()
    else:
        logger.error("SIM: Bot not in SEARCHING state as expected after stop-loss. Check logic.")

    logger.info("\n===== BOT SIMULATION END =====")
