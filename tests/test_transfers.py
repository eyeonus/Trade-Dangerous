from types import SimpleNamespace

import pytest

from tradedangerous.tradeenv import TradeEnv
from tradedangerous.tradeexcept import TradeException
from tradedangerous import transfers

class _Response:
    def __init__(self, chunks, *, headers=None):
        self._chunks = list(chunks)
        self.headers = headers or {
            'content-length': str(sum(len(chunk) for chunk in self._chunks)),
            'content-encoding': 'identity',
        }
    
    def iter_content(self, chunk_size=4096):
        del chunk_size
        yield from self._chunks
    
    def raise_for_status(self):
        return None
    
    def close(self):
        return None

class _Session:
    def __init__(self, response):
        self.response = response
        self.calls = []
    
    def get(self, url, headers=None, stream=True, timeout=30):
        self.calls.append({
            'url': url,
            'headers': headers,
            'stream': stream,
            'timeout': timeout,
        })
        return self.response

class _Monitor:
    def __init__(self, *, stop=False):
        self.status = []
        self.stop = stop
    
    def set_status(self, text):
        self.status.append(text)
    
    def stop_requested(self):
        return self.stop

def _make_env(tmp_path, *, quiet=1, detail=0, monitor=None):
    env = TradeEnv(tmpDir=str(tmp_path / 'tmp'), quiet=quiet, detail=detail, color=False)
    if monitor is not None:
        env.import_monitor = monitor
    return env

def test_transfers_split_unit_makeUnit_and_filename_extraction():
    assert transfers.split_unit(999) == ('999', 'B')
    assert transfers.split_unit(2048) == ('2.0', 'KB')
    assert transfers.makeUnit(2048) == '2.0KB'
    assert transfers.get_filename_from_url('https://example.invalid/files/data%20dump.csv') == 'data dump.csv'

def test_transfers_download_writes_temp_file_then_renames(tmp_path):
    response = _Response([b'abc', b'def'])
    session = _Session(response)
    env = _make_env(tmp_path)
    target = tmp_path / 'data' / 'import.prices'
    
    headers = transfers.download(
        env,
        'https://example.invalid/import.prices',
        target,
        session=session,
    )
    
    assert target.read_bytes() == b'abcdef'
    assert not (tmp_path / 'tmp' / 'import.prices.dl').exists()
    assert headers['content-length'] == '6'
    assert session.calls[0]['url'] == 'https://example.invalid/import.prices'

def test_transfers_download_honours_import_monitor_stop(tmp_path):
    monitor = _Monitor(stop=True)
    response = _Response([b'abc'])
    env = _make_env(tmp_path, monitor=monitor)
    
    with pytest.raises(TradeException, match='Import stopped by user'):
        transfers.download(
            env,
            'https://example.invalid/import.prices',
            tmp_path / 'import.prices',
            session=_Session(response),
        )
    
    assert monitor.status == ['Downloading import.prices...']
