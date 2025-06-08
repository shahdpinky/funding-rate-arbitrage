#!/usr/bin/env python3
"""
Test script to validate current Hyperliquid SDK compatibility
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'hyperliq'))

try:
    # Test new SDK imports
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    print("✓ New SDK imports successful")
    
    # Test if constants exist
    print(f"✓ Testnet URL: {constants.TESTNET_API_URL}")
    print(f"✓ Mainnet URL: {constants.MAINNET_API_URL}")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test environment variables (without values)
from dotenv import load_dotenv
load_dotenv()

wallet_address = os.getenv("WALLET_ADDRESS")
private_key = os.getenv("PRIVATE_KEY")

if not wallet_address or not private_key:
    print("⚠ Environment variables not set (WALLET_ADDRESS, PRIVATE_KEY)")
    print("Please copy .env.example to .env and configure your credentials")
    sys.exit(1)

# Test connection without orders
try:
    import eth_account
    from eth_account.signers.local import LocalAccount
    
    # Test account setup
    account: LocalAccount = eth_account.Account.from_key(private_key)
    print(f"✓ Account setup successful")
    
    # Test info connection (testnet)
    info = Info(constants.TESTNET_API_URL, skip_ws=True)
    print("✓ Info object created")
    
    # Test user state
    user_state = info.user_state(wallet_address)
    margin_summary = user_state["marginSummary"]
    account_value = float(margin_summary["accountValue"])
    
    print(f"✓ Connection successful! Account value: ${account_value}")
    
    if account_value == 0:
        print("⚠ Account has no equity on testnet")
    
except Exception as e:
    print(f"✗ Connection failed: {e}")
    sys.exit(1)

print("\n🎉 All tests passed! Hyperliquid SDK is working correctly.")