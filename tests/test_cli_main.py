from tradedangerous.plugins import PluginException
from tradedangerous.tradeexcept import TradeException


def test_cli_main_returns_1_on_trade_or_plugin_exception(monkeypatch, capsys):
    import tradedangerous.cli as cli

    monkeypatch.setattr(cli, 'trade', lambda argv: (_ for _ in ()).throw(TradeException('boom')))
    result = cli.main(['trade.py', 'run'])
    captured = capsys.readouterr()
    assert result == 1
    assert 'trade.py: boom' in captured.out

    monkeypatch.setattr(cli, 'trade', lambda argv: (_ for _ in ()).throw(PluginException('kaput')))
    result = cli.main(['trade.py', 'import'])
    captured = capsys.readouterr()
    assert result == 1
    assert 'PLUGIN ERROR: kaput' in captured.out


def test_cli_main_handles_unicode_error_fallback(monkeypatch, capsys):
    import tradedangerous.cli as cli

    monkeypatch.setattr(cli, 'trade', lambda argv: (_ for _ in ()).throw(UnicodeEncodeError('ascii', 'x', 0, 1, 'fail')))

    result = cli.main(['trade.py', 'run'])
    captured = capsys.readouterr()

    assert result == 1
    assert 'Unexpected unicode error in the wild!' in captured.out
