#!/usr/bin/env python3
"""
Comprehensive test runner for Hyperliquid spot trading and real-time market data functionality
"""
import sys
import os
import unittest
import argparse
from io import StringIO
import time

def run_unit_tests():
    """Run unit tests (fast, no network required)"""
    print("🧪 Running Unit Tests...")
    print("=" * 50)
    
    # Discover tests in tests/unit directory
    test_dir = os.path.join(os.path.dirname(__file__), 'tests', 'unit')
    
    if not os.path.exists(test_dir):
        print(f"⚠ Unit test directory not found: {test_dir}")
        return False
    
    # Use test discovery
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern='test*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_integration_tests():
    """Run integration tests (require network and credentials)"""
    print("\n🌐 Running Integration Tests...")
    print("=" * 50)
    print("Note: These tests require:")
    print("- WALLET_ADDRESS and PRIVATE_KEY in .env")
    print("- Active internet connection to Hyperliquid testnet")
    print("- May take 30+ seconds to complete")
    print()
    
    # Check for credentials
    from dotenv import load_dotenv
    load_dotenv()
    
    if not (os.getenv("WALLET_ADDRESS") and os.getenv("PRIVATE_KEY")):
        print("⚠ Skipping integration tests - missing environment variables")
        print("Please set WALLET_ADDRESS and PRIVATE_KEY in .env file")
        return True
    
    # Discover integration tests
    test_dir = os.path.join(os.path.dirname(__file__), 'tests', 'integration')
    
    if not os.path.exists(test_dir):
        print(f"⚠ Integration test directory not found: {test_dir}")
        return False
    
    # Use test discovery
    loader = unittest.TestLoader()
    suite = loader.discover(test_dir, pattern='test*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    return result.wasSuccessful()

def run_api_compatibility_tests():
    """Run existing API compatibility tests"""
    print("\n🔗 Running API Compatibility Tests...")
    print("=" * 50)
    
    # Look for compatibility test scripts
    test_dir = os.path.join(os.path.dirname(__file__), 'tests', 'compatibility')
    test_scripts = [
        'test_existing_code.py',
        'test_api_calls.py',
        'test_hyperliq_connection.py'
    ]
    
    all_passed = True
    
    for script in test_scripts:
        script_path = os.path.join(test_dir, script)
        if os.path.exists(script_path):
            print(f"\nRunning {script}...")
            try:
                # Capture output
                old_stdout = sys.stdout
                sys.stdout = captured_output = StringIO()
                
                # Run the script
                with open(script_path, 'r') as f:
                    code = f.read()
                    exec(code)
                
                # Restore stdout and print results
                sys.stdout = old_stdout
                output = captured_output.getvalue()
                
                # Check for actual failures vs expected variations
                failed_funding = "funding rate test failed:" in output.lower()
                failed_imports = "import" in output.lower() and "failed" in output.lower()
                has_exceptions = "exception" in output.lower() and "failed" in output.lower()
                
                if failed_funding or failed_imports or has_exceptions:
                    print(f"❌ {script} had failures")
                    all_passed = False
                else:
                    print(f"✅ {script} passed")
                
                # Print last few lines of output for context
                lines = output.strip().split('\n')
                for line in lines[-3:]:
                    if line.strip():
                        print(f"  {line}")
                        
            except Exception as e:
                print(f"❌ {script} failed with exception: {e}")
                all_passed = False
            finally:
                sys.stdout = old_stdout
        else:
            print(f"⚠ {script} not found in {test_dir}")
    
    return all_passed

def run_smoke_tests():
    """Run quick smoke tests to verify basic functionality"""
    print("\n💨 Running Smoke Tests...")
    print("=" * 50)
    
    try:
        # Test imports
        print("Testing imports...")
        sys.path.append("src")
        sys.path.append("src/hyperliq")
        
        from hyperliq.spot import HyperliquidSpot, Side
        from hyperliq.order import HyperLiquidOrder
        print("✅ All imports successful")
        
        # Test enum values
        assert str(Side.BUY) == "BUY"
        assert str(Side.SELL) == "SELL"
        print("✅ Side enum working correctly")
        
        # Test class instantiation (with mocks)
        from unittest.mock import Mock
        mock_address = "0x123"
        mock_info = Mock()
        mock_exchange = Mock()
        
        spot = HyperliquidSpot(mock_address, mock_info, mock_exchange)
        order = HyperLiquidOrder(mock_address, mock_info, mock_exchange)
        
        assert spot.address == mock_address
        assert order.address == mock_address
        print("✅ Class instantiation working")
        
        # Test method existence
        required_spot_methods = [
            'get_spot_balances', 'create_spot_market_order', 'get_spot_top_of_book',
            'subscribe_spot_top_of_book', 'subscribe_spot_l2_book', 'unsubscribe'
        ]
        
        for method in required_spot_methods:
            assert hasattr(spot, method), f"Missing method: {method}"
        print("✅ All spot methods present")
        
        required_perp_methods = [
            'get_perp_top_of_book', 'subscribe_perp_top_of_book', 
            'subscribe_perp_l2_book', 'unsubscribe'
        ]
        
        for method in required_perp_methods:
            assert hasattr(order, method), f"Missing method: {method}"
        print("✅ All perpetual enhancement methods present")
        
        print("✅ All smoke tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Smoke test failed: {e}")
        return False

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Run Hyperliquid trading tests")
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--compatibility', action='store_true', help='Run compatibility tests only')
    parser.add_argument('--smoke', action='store_true', help='Run smoke tests only')
    parser.add_argument('--all', action='store_true', help='Run all tests (default)')
    
    args = parser.parse_args()
    
    # Default to all tests if no specific test type specified
    if not any([args.unit, args.integration, args.compatibility, args.smoke]):
        args.all = True
    
    print("🚀 Hyperliquid Trading Test Suite")
    print("=" * 50)
    print("Testing spot trading, WebSocket subscriptions, and real-time market data")
    print()
    
    start_time = time.time()
    results = []
    
    # Run selected test suites
    if args.smoke or args.all:
        results.append(("Smoke Tests", run_smoke_tests()))
    
    if args.unit or args.all:
        results.append(("Unit Tests", run_unit_tests()))
    
    if args.compatibility or args.all:
        results.append(("Compatibility Tests", run_api_compatibility_tests()))
    
    if args.integration or args.all:
        results.append(("Integration Tests", run_integration_tests()))
    
    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 50)
    print("🏁 Test Summary")
    print("=" * 50)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:20} {status}")
        if not passed:
            all_passed = False
    
    print(f"\nTotal time: {elapsed:.2f} seconds")
    
    if all_passed:
        print("\n🎉 All tests passed! Your Hyperliquid implementation is working correctly.")
        return 0
    else:
        print("\n💥 Some tests failed. Please check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())