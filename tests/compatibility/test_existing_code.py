#!/usr/bin/env python3
"""
Test existing Hyperliquid code compatibility
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'hyperliq'))

print("Testing existing code imports...")

try:
    # Test your existing utilities
    import hyperliq_utils
    print("✓ hyperliq_utils import successful")
    
    # Test function access
    get_meta_data = getattr(hyperliq_utils, 'get_meta_data', None)
    hyperliquid_setup = getattr(hyperliq_utils, 'hyperliquid_setup', None)
    
    if get_meta_data:
        print("✓ get_meta_data function found")
    if hyperliquid_setup:
        print("✓ hyperliquid_setup function found")
        
except ImportError as e:
    print(f"✗ hyperliq_utils import failed: {e}")

try:
    # Test funding rate module
    from hyperliq.funding_rate import HyperliquidFundingRates
    print("✓ HyperliquidFundingRates import successful")
    
except ImportError as e:
    print(f"✗ HyperliquidFundingRates import failed: {e}")

try:
    # Test order module
    from hyperliq.order import HyperLiquidOrder
    print("✓ HyperLiquidOrder import successful")
    
except ImportError as e:
    print(f"✗ HyperLiquidOrder import failed: {e}")

print("\n📋 Import test complete")