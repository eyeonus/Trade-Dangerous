import importlib

from tradedangerous.plugins import PluginException
from tradedangerous.tradeexcept import TradeException


def test_cli_main_returns_1_on_trade_or_plugin_exception(monkeypatch, capsys):
    import tradedangerous.cli as cli

    module = importlib.reload(cli)

    monkeypatch.setattr(module, 'trade', lambda argv: (_ for _ in ()).throw(TradeException('boom')))
    result = module.main(['trade.py', 'run'])
    captured = capsys.readouterr()
    assert result == 1
    assert 'trade.py: boom' in captured.out

    monkeypatch.setattr(module, 'trade', lambda argv: (_ for _ in ()).throw(PluginException('kaput')))
    result = module.main(['trade.py', 'import'])
    captured = capsys.readouterr()
    assert result == 1
    assert 'PLUGIN ERROR: kaput' in captured.out


def test_cli_main_handles_unicode_error_fallback(monkeypatch, capsys):
    import tradedangerous.cli as cli

    module = importlib.reload(cli)
    monkeypatch.setattr(module, 'trade', lambda argv: (_ for _ in ()).throw(UnicodeEncodeError('ascii', 'x', 0, 1, 'fail')))

    result = module.main(['trade.py', 'run'])
    captured = capsys.readouterr()

    assert result == 1
    assert 'Unexpected unicode error in the wild!' in captured.out
