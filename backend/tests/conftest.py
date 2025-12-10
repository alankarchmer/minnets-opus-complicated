"""Pytest configuration for backend tests."""

import pytest

# Configure pytest-asyncio to auto mode for easier async test handling
pytest_plugins = ["pytest_asyncio"]


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
