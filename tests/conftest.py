import gc
import pytest
import typing

from .helpers import tdenv, touch
from tradedangerous.tradedb import TradeDB


# def pytest_sessionstart(session):
#     # setup_stuff
#     copy_fixtures(tdenv.dataDir)

@pytest.fixture(scope="module")
def tdb() -> typing.Generator[TradeDB, None, None]:
    instance = TradeDB()
    yield instance
    # closing tdb when done with it
    instance.close(final=True)
    del instance
    # Make sure we aren't holding on to any handles
    gc.collect()


@pytest.fixture(scope="module")
def touchdb():
    return touch(tdenv.dataDir, 'TradeDangerous.db')


def pytest_addoption(parser):
    parser.addoption(
        "--runslow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--runsuperslow", action="store_true", default=False, help="run superslow tests"
    )


def pytest_collection_modifyitems(config, items):
    has_runslow = config.getoption("--runslow")
    has_runsuperslow = config.getoption("--runsuperslow")
    
    skip_slow = pytest.mark.skip(reason="need --runslow option to run")
    skip_superslow = pytest.mark.skip(reason="need --runsuperslow option to run")
    for item in items:
        if "slow" in item.keywords and not has_runslow:
            item.add_marker(skip_slow)
        if "superslow" in item.keywords and not has_runsuperslow:
            item.add_marker(skip_superslow)
