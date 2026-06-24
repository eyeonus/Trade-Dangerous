"""CLI backend-selection contract for cli.trade().

The two-tier ORM model: a command declaring Needs.RESOLVER gets a TradeORM
handle; a Needs.NOTHING command gets no backend at all. Preflight validation runs
before any backend is constructed. There is no legacy TradeDB path.
"""
import contextlib
from types import SimpleNamespace

import pytest

from tradedangerous import cli, tradeexcept


def _make_dummy_index(env_cls):
    class DummyCmdIndex:
        def parse(self, argv):
            return env_cls()
    return DummyCmdIndex


def _must_not_construct(*args, **kwargs):
    raise AssertionError("a backend was constructed when it should not have been")


class _BaseEnv:
    """Minimal CommandEnv stand-in for the cli.trade() backend-selection path."""
    needs_resolver = False
    usesTradeData = False
    _cmd = SimpleNamespace(allowMissingDB=False)

    def preflight(self):
        pass

    def DEBUG0(self, *args, **kwargs):
        pass

    @contextlib.contextmanager
    def time_block(self, *args, **kwargs):
        yield


def test_cli_preflight_runs_before_backend(monkeypatch):
    """Preflight runs before the backend handle is built, which is built before
    the command runs."""
    calls = []

    class DummyORM:
        def close(self, final=False):
            pass

    class DummyEnv(_BaseEnv):
        needs_resolver = True

        def preflight(self):
            calls.append("preflight")

        def run(self, tdb):
            calls.append("run")

    def _orm(**kwargs):
        calls.append("TradeORM")
        return DummyORM()

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", _orm)

    cli.trade(["trade", "anything"])

    assert calls.index("preflight") < calls.index("TradeORM") < calls.index("run")


def test_cli_preflight_failure_skips_backend(monkeypatch):
    """A failing preflight aborts before any backend is constructed."""
    class DummyEnv(_BaseEnv):
        needs_resolver = True

        def preflight(self):
            raise tradeexcept.TradeException("boom")

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", _must_not_construct)

    with pytest.raises(tradeexcept.TradeException):
        cli.trade(["trade", "anything"])


def test_cli_backend_nothing_constructs_no_orm(monkeypatch):
    """needs_resolver False: no backend is constructed; run() gets tdb=None."""
    received = []

    class DummyEnv(_BaseEnv):
        needs_resolver = False

        def run(self, tdb):
            received.append(tdb)

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", _must_not_construct)

    cli.trade(["trade", "anything"])

    assert received == [None]


def test_cli_backend_resolver_constructs_orm(monkeypatch):
    """needs_resolver True: TradeORM is constructed, handed to run(), then closed."""
    calls = []

    class DummyORM:
        def close(self, final=False):
            calls.append(("orm_close", final))

    class DummyEnv(_BaseEnv):
        needs_resolver = True

        def run(self, tdb):
            calls.append(("run", type(tdb).__name__))

    def _orm(**kwargs):
        calls.append(("TradeORM",))
        return DummyORM()

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", _orm)

    cli.trade(["trade", "anything"])

    assert ("TradeORM",) in calls
    assert ("run", "DummyORM") in calls
    assert ("orm_close", True) in calls
