import eth_account
from eth_account.signers.local import LocalAccount
import os
from dotenv import load_dotenv
import requests
import json

from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

load_dotenv()


def hyperliquid_setup(base_url=None, skip_ws=False):
    """
    Sets up the connection to the Hyperliquid API.

    This function relies on the following environment variables:
    - PRIVATE_KEY: The private key of the wallet to use.
    - WALLET_ADDRESS: The address of the wallet to use.

    Parameters:
    base_url (str, optional): The base URL of the Hyperliquid API. Defaults to None.
    skip_ws (bool, optional): Whether to skip the WebSocket connection. Defaults to False.

    Returns:
    tuple: A tuple containing the address, info object, and exchange object.
    """
    # Get address
    account: LocalAccount = eth_account.Account.from_key(os.getenv("PRIVATE_KEY"))
    address = os.getenv("WALLET_ADDRESS")

    # Get info
    info = Info(base_url, skip_ws)
    user_state = info.user_state(address)
    margin_summary = user_state["marginSummary"]
    if float(margin_summary["accountValue"]) == 0:
        print("Not running the example because the provided account has no equity.")
        url = info.base_url.split(".", 1)[1]
        error_string = f"No accountValue:\nIf you think this is a mistake, make sure that {address} has a balance on {url}.\nIf address shown is your API wallet address, update the config to specify the address of your account, not the address of the API wallet."
        raise Exception(error_string)

    # Get exchange
    exchange = Exchange(account, base_url, account_address=address)

    return address, info, exchange


def get_meta_data(base_url=constants.TESTNET_API_URL):
    """
    Retrieves meta data for all tradeable perps on Hyperliquid

    Hyperliquid doesn't have this API call in their SDK
    """

    # API endpoint
    url = base_url + "/info"

    # Headers required for the request
    headers = {"Content-Type": "application/json"}

    # Request body data
    body = {
        "type": "metaAndAssetCtxs",
    }

    try:
        # Sending POST request to the API
        response = requests.post(url, headers=headers, data=json.dumps(body))
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error getting metadata: {e}")
        return None

