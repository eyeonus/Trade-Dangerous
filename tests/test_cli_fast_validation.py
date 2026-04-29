import contextlib
import pytest

from tradedangerous import cli


def _make_dummy_index(env_cls):
    class DummyCmdIndex:
        def parse(self, argv):
            return env_cls()
    return DummyCmdIndex


def test_cli_trade_fast_validation_runs_before_tradedb_load(monkeypatch):
    class DummyEnv:
        needs_resolver  = False
        needs_legacy_db = True
        needs_full_load = True
        usesTradeData   = False

        def preflight(self):
            raise cli.tradeexcept.TradeException("boom")

        def DEBUG0(self, *args, **kwargs):
            pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs):
            yield

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))

    def _should_not_be_constructed(*args, **kwargs):
        raise AssertionError("No backend must be constructed when preflight fails")

    monkeypatch.setattr(cli.tradedb, "TradeDB", _should_not_be_constructed)
    monkeypatch.setattr(cli, "TradeORM", _should_not_be_constructed)

    with pytest.raises(cli.tradeexcept.TradeException):
        cli.trade(["trade", "anything"])


def test_cli_trade_calls_preflight_before_tradedb(monkeypatch):
    calls = []

    class DummyTDB:
        def close(self, final=False):
            calls.append(("close", final))

    class DummyEnv:
        needs_resolver  = False
        needs_legacy_db = True
        needs_full_load = True
        usesTradeData   = False

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

    def _TradeDB(cmdenv, load=True):
        calls.append(("TradeDB", load))
        assert calls[0] == ("preflight",)
        return DummyTDB()

    def _torm_must_not_be_constructed(**kwargs):
        raise AssertionError("TradeORM must not be constructed for legacy-path commands")

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli.tradedb, "TradeDB", _TradeDB)
    monkeypatch.setattr(cli, "TradeORM", _torm_must_not_be_constructed)

    cli.trade(["trade", "anything"])

    assert calls[0] == ("preflight",)
    assert calls[1] == ("TradeDB", True)
    assert ("run", True) in calls
    assert ("close", True) in calls


def test_cli_trade_preflight_can_disable_db_load(monkeypatch):
    class DummyTDB:
        def close(self, final=False):
            pass

    class DummyEnv:
        needs_resolver  = False
        needs_legacy_db = True
        needs_full_load = True
        usesTradeData   = False

        def preflight(self):
            self.needs_full_load = False

        def run(self, tdb):
            return None  # noqa

        def DEBUG0(self, *args, **kwargs):
            pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs):
            yield

    def _TradeDB(cmdenv, load=True):
        assert load is False
        return DummyTDB()

    def _torm_must_not_be_constructed(**kwargs):
        raise AssertionError("TradeORM must not be constructed for legacy-path commands")

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli.tradedb, "TradeDB", _TradeDB)
    monkeypatch.setattr(cli, "TradeORM", _torm_must_not_be_constructed)

    cli.trade(["trade", "anything"])


def test_cli_backend_nothing_constructs_no_db(monkeypatch):
    """Needs.NOTHING: neither TradeORM nor TradeDB is constructed."""
    received = []

    class DummyEnv:
        needs_resolver  = False
        needs_legacy_db = False
        needs_full_load = False
        usesTradeData   = False

        def preflight(self): pass

        def run(self, tdb):
            received.append(tdb)
            return None

        def DEBUG0(self, *args, **kwargs): pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs): yield

    def _must_not_construct(*args, **kwargs):
        raise AssertionError("No backend must be constructed for Needs.NOTHING")

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", _must_not_construct)
    monkeypatch.setattr(cli.tradedb, "TradeDB", _must_not_construct)

    cli.trade(["trade", "anything"])

    assert received == [None]


def test_cli_backend_resolver_constructs_orm_only(monkeypatch):
    """Needs.RESOLVER: TradeORM is constructed; TradeDB is not."""
    calls = []

    class DummyORM:
        def close(self, final=False):
            calls.append(("orm_close",))

    class DummyEnv:
        needs_resolver  = True
        needs_legacy_db = False
        needs_full_load = False
        usesTradeData   = False

        def preflight(self): pass

        def run(self, tdb):
            calls.append(("run", type(tdb).__name__))
            return None

        def DEBUG0(self, *args, **kwargs): pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs): yield

    def _tdb_must_not_be_constructed(*args, **kwargs):
        raise AssertionError("TradeDB must not be constructed for Needs.RESOLVER")

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", lambda **kwargs: DummyORM())
    monkeypatch.setattr(cli.tradedb, "TradeDB", _tdb_must_not_be_constructed)

    cli.trade(["trade", "anything"])

    assert ("run", "DummyORM") in calls
    assert ("orm_close",) in calls


def test_cli_backend_legacy_handle_constructs_tdb_no_orm(monkeypatch):
    """Needs.LEGACY_HANDLE: TradeDB(load=False) constructed; TradeORM is not."""
    calls = []

    class DummyTDB:
        def close(self, final=False):
            calls.append(("tdb_close", final))

    class DummyEnv:
        needs_resolver  = False
        needs_legacy_db = True
        needs_full_load = False
        usesTradeData   = False

        def preflight(self): pass

        def run(self, tdb):
            calls.append(("run", type(tdb).__name__))
            return None

        def DEBUG0(self, *args, **kwargs): pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs): yield

    def _torm_must_not_be_constructed(**kwargs):
        raise AssertionError("TradeORM must not be constructed for Needs.LEGACY_HANDLE")

    def _TradeDB(cmdenv, load=True):
        calls.append(("TradeDB", load))
        return DummyTDB()

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", _torm_must_not_be_constructed)
    monkeypatch.setattr(cli.tradedb, "TradeDB", _TradeDB)

    cli.trade(["trade", "anything"])

    assert ("TradeDB", False) in calls
    assert ("run", "DummyTDB") in calls
    assert ("tdb_close", True) in calls


def test_cli_backend_full_legacy_constructs_tdb_with_load(monkeypatch):
    """Needs.FULL_LEGACY: TradeDB(load=True) constructed; TradeORM is not."""
    calls = []

    class DummyTDB:
        def close(self, final=False):
            calls.append(("tdb_close", final))

    class DummyEnv:
        needs_resolver  = False
        needs_legacy_db = True
        needs_full_load = True
        usesTradeData   = False

        def preflight(self): pass

        def run(self, tdb):
            calls.append(("run", type(tdb).__name__))
            return None

        def DEBUG0(self, *args, **kwargs): pass

        @contextlib.contextmanager
        def time_block(self, *args, **kwargs): yield

    def _torm_must_not_be_constructed(**kwargs):
        raise AssertionError("TradeORM must not be constructed for Needs.FULL_LEGACY")

    def _TradeDB(cmdenv, load=True):
        calls.append(("TradeDB", load))
        return DummyTDB()

    monkeypatch.setattr(cli.commands, "CommandIndex", _make_dummy_index(DummyEnv))
    monkeypatch.setattr(cli, "TradeORM", _torm_must_not_be_constructed)
    monkeypatch.setattr(cli.tradedb, "TradeDB", _TradeDB)

    cli.trade(["trade", "anything"])

    assert ("TradeDB", True) in calls
    assert ("run", "DummyTDB") in calls
    assert ("tdb_close", True) in calls
