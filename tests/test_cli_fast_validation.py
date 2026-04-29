import contextlib
import pytest

from tradedangerous import cli


def test_cli_trade_fast_validation_runs_before_tradedb_load(monkeypatch):
    class DummyEnv:
        needs_legacy_db = True
        needs_full_load = True
        usesTradeData = False

        def preflight(self):
            raise cli.tradeexcept.TradeException("boom")

        def DEBUG0(self, *args, **kwargs):
            pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs):
            yield

    class DummyCmdIndex:
        def parse(self, argv):
            return DummyEnv()

    monkeypatch.setattr(cli.commands, "CommandIndex", DummyCmdIndex)

    # If TradeDB() is called at all, this test should fail
    def _tdb_should_not_be_constructed(*args, **kwargs):
        raise AssertionError("TradeDB must not be constructed when preflight fails")

    monkeypatch.setattr(cli.tradedb, "TradeDB", _tdb_should_not_be_constructed)

    with pytest.raises(cli.tradeexcept.TradeException):
        cli.trade(["trade", "anything"])


def test_cli_trade_calls_preflight_before_tradedb(monkeypatch):
    calls = []

    class DummyORM:
        def close(self, final=False):
            pass

    class DummyTDB:
        def close(self, final=False):
            calls.append(("close", final))

    class DummyEnv:
        needs_legacy_db = True
        needs_full_load = True
        usesTradeData = False

        def preflight(self):
            calls.append(("preflight",))

        def run(self, tdb):
            calls.append(("run", isinstance(tdb, DummyTDB)))
            return None  # noqa

        def DEBUG0(self, *args, **kwargs):
            pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs):
            yield

    class DummyCmdIndex:
        def parse(self, argv):
            return DummyEnv()

    def _TradeDB(cmdenv, load=True):
        calls.append(("TradeDB", load))
        # preflight must have happened first
        assert calls[0] == ("preflight",)
        return DummyTDB()

    monkeypatch.setattr(cli.commands, "CommandIndex", DummyCmdIndex)
    monkeypatch.setattr(cli.tradedb, "TradeDB", _TradeDB)
    monkeypatch.setattr(cli, "TradeORM", lambda **kwargs: DummyORM())

    cli.trade(["trade", "anything"])

    assert calls[0] == ("preflight",)
    assert calls[1] == ("TradeDB", True)
    assert ("run", True) in calls
    assert ("close", True) in calls


def test_cli_trade_preflight_can_disable_db_load(monkeypatch):
    class DummyORM:
        def close(self, final=False):
            pass

    class DummyTDB:
        def close(self, final=False):
            pass

    class DummyEnv:
        needs_legacy_db = True
        needs_full_load = True
        usesTradeData = False

        def preflight(self):
            # simulate a fast validator deciding a full preload isn't needed
            self.needs_full_load = False

        def run(self, tdb):
            return None  # noqa

        def DEBUG0(self, *args, **kwargs):
            pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs):
            yield

    class DummyCmdIndex:
        def parse(self, argv):
            return DummyEnv()

    def _TradeDB(cmdenv, load=True):
        assert load is False
        return DummyTDB()

    monkeypatch.setattr(cli.commands, "CommandIndex", DummyCmdIndex)
    monkeypatch.setattr(cli.tradedb, "TradeDB", _TradeDB)
    monkeypatch.setattr(cli, "TradeORM", lambda **kwargs: DummyORM())

    cli.trade(["trade", "anything"])
