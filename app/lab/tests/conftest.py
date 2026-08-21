import logging

import pytest


@pytest.fixture
def caplog(caplog):
    """Configure caplog for all tests."""
    caplog.set_level(logging.INFO)
    return caplog
