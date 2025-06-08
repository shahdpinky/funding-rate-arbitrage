import time
from datetime import timedelta

THIRTY_MINUTES_IN_MS = int(timedelta(minutes=30).total_seconds() * 1000)


class HyperliquidFundingRates(object):
    def __init__(self, info):
        """
        Parameters:
        info (object): An object to interact with Hyperliquid's API.
        """
        self.info = info

    def get_funding_history(
        self, symbol: str, start_time: int = None
    ) -> dict:
        """
        Retrieves the funding history for a given symbol.

        Parameters:
        symbol (str): The trading symbol for which to retrieve funding history (e.g., "BTC").
        start_time (int): The start time in milliseconds since the epoch. Defaults to 30 minutes ago.

        Returns:
        dict: The funding history for the specified symbol.
        """
        if start_time is None:
            start_time = int(time.time() * 1000) - THIRTY_MINUTES_IN_MS

        try:
            return self.info.funding_history(symbol, start_time)
        except Exception as e:
            print(f"Error getting funding history for {symbol}: {e}")
            return {}

    def get_hyperliquid_funding_rates(self) -> dict:
        """
        Fetches asset names and their corresponding funding rates from the API.

        Returns:
        dict: A dictionary where the symbol is the key and the 8-hour funding rate is the value.
        """
        try:
            meta_data = self.info.meta()
            asset_info = meta_data["universe"]

            assets_to_funding_rates = {}
            for asset in asset_info:
                symbol = asset["name"]
                # The funding rate is hourly, so we multiply by 8 to get the 8-hour funding rate.
                funding_rate = float(asset["funding"]) * 8
                assets_to_funding_rates[symbol] = funding_rate

            return assets_to_funding_rates
        except Exception as e:
            print(f"Error getting funding rates: {e}")
            return {}
