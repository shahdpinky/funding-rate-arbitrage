"""
Pytest configuration and shared fixtures
"""
import sys
import os
import pytest

# Add project paths for test imports
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))
sys.path.insert(0, os.path.join(project_root, 'src', 'hyperliq'))

@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory"""
    return os.path.dirname(os.path.dirname(__file__))

@pytest.fixture
def mock_hyperliquid_setup():
    """Mock Hyperliquid setup for testing"""
    from unittest.mock import Mock
    
    mock_address = "0x1234567890abcdef"
    mock_info = Mock()
    mock_exchange = Mock()
    
    return mock_address, mock_info, mock_exchange

def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, no network)"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require network)"
    )
    config.addinivalue_line(
        "markers", "compatibility: marks tests as compatibility tests"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow running"
    )