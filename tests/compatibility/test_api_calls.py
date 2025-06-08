#!/usr/bin/env python3
"""
Test API calls that don't require authentication
"""
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, os.path.join(project_root, 'src', 'hyperliq'))

print("Testing public API calls...")

try:
    # Test metadata call (no auth required)
    import hyperliq_utils
    
    print("Calling get_meta_data()...")
    meta_data = hyperliq_utils.get_meta_data()
    
    if isinstance(meta_data, dict):
        print("✓ get_meta_data() successful")
        
        # Check structure
        if 'universe' in meta_data:
            print(f"✓ Found {len(meta_data['universe'])} tradeable assets")
            
            # Show first few assets
            for i, asset in enumerate(meta_data['universe'][:3]):
                if 'name' in asset:
                    print(f"  - {asset['name']}")
        else:
            print("⚠ Response structure may have changed")
            print(f"Keys found: {list(meta_data.keys())}")
    else:
        print(f"✗ Unexpected response type: {type(meta_data)}")
        print(f"Response: {meta_data}")
        
except Exception as e:
    print(f"✗ get_meta_data() failed: {e}")

print("\nTesting funding rate fetching...")

try:
    from hyperliq.funding_rate import HyperliquidFundingRates
    from unittest.mock import Mock
    
    # Create mock objects since this test doesn't need real ones
    mock_info = Mock()
    
    hr = HyperliquidFundingRates(mock_info)
    print("✓ HyperliquidFundingRates created")
    
    # Try to get funding rates (uses static utility function)
    funding_rates = hr.get_hyperliquid_funding_rates()
    print(f"✓ Funding rates fetched: {len(funding_rates)} assets")
    
    # Show first few
    for symbol, rate in list(funding_rates.items())[:3]:
        print(f"  {symbol}: {rate}")
        
except Exception as e:
    print(f"⚠ Funding rate test failed: {e}")

print("\n📋 API test complete")