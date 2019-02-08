import pytest
from .helpers import copy_fixtures, tdenv, touch
from tradedangerous.tradedb import TradeDB


# def pytest_sessionstart(session):
#     # setup_stuff
#     copy_fixtures(tdenv.dataDir)

@pytest.fixture(scope="module")
def tdb():
    return TradeDB()

@pytest.fixture(scope="module")
def touchdb():
    return touch(tdenv.dataDir, 'TradeDangerous.db')

def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runslow"):
        # --runslow given in cli: do not skip slow tests
        return
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    skip_superslow = pytest.mark.skip(reason="need --runsuperslow option to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
        if "superslow" in item.keywords:
            item.add_marker(skip_superslow)
