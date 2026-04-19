"""
Pytest configuration and shared fixtures for PFP API tests
"""
import pytest
import os

# Set environment variable for tests
os.environ.setdefault('REACT_APP_BACKEND_URL', 'https://fea-crypto.preview.emergentagent.com')


@pytest.fixture(scope="session")
def base_url():
    """Get the base URL for API tests"""
    return os.environ.get('REACT_APP_BACKEND_URL', 'https://fea-crypto.preview.emergentagent.com').rstrip('/')
