import json
from pathlib import Path
from types import SimpleNamespace

from tradedangerous import TradeEnv
from tradedangerous.plugins.eddblink_plug import ImportPlugin as EddblinkImportPlugin
from tradedangerous.plugins.eddblink_plug import _count_listing_entries
from tradedangerous.plugins.spansh_plug import ImportPlugin as SpanshImportPlugin

def _make_tdenv(tmp_path, *, plugin_options=None):
    return TradeEnv(
        properties={'pluginOptions': plugin_options or []},
        dataDir=str(tmp_path / 'data'),
        tmpDir=str(tmp_path / 'tmp'),
        quiet=1,
    )

def _make_tdb(tmp_path):
    return SimpleNamespace(
        dataPath=(tmp_path / 'data'),
        dataDir=str(tmp_path / 'data'),
        data_dir=(tmp_path / 'data'),
        tmpDir=str(tmp_path / 'tmp'),
    )

def test_eddblink_count_listing_entries_handles_missing_header_only_and_normal_files(tmp_path):
    tdenv = _make_tdenv(tmp_path)
    missing = tmp_path / 'missing.csv'
    empty = tmp_path / 'empty.csv'
    header_only = tmp_path / 'header.csv'
    normal = tmp_path / 'normal.csv'
    
    empty.write_text('', encoding='utf-8')
    header_only.write_text('id,station,item\n', encoding='utf-8')
    normal.write_text('id,station,item\n1,2,3\n4,5,6\n', encoding='utf-8')
    
    assert _count_listing_entries(tdenv, missing) == 0
    assert _count_listing_entries(tdenv, empty) == 0
    assert _count_listing_entries(tdenv, header_only) == 0
    assert _count_listing_entries(tdenv, normal) == 4

def test_eddblink_state_file_missing_returns_empty_state(tmp_path):
    plugin = EddblinkImportPlugin(_make_tdb(tmp_path), _make_tdenv(tmp_path))
    
    state = plugin._load_eddblink_state()
    
    assert state == {'version': 1, 'files': {}}

def test_eddblink_state_file_corrupt_returns_empty_state(tmp_path):
    plugin = EddblinkImportPlugin(_make_tdb(tmp_path), _make_tdenv(tmp_path))
    state_path = plugin._eddblink_state_path()
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{not-json', encoding='utf-8')
    
    state = plugin._load_eddblink_state()
    
    assert state == {'version': 1, 'files': {}}

def test_eddblink_state_save_creates_parent_and_writes_valid_json(tmp_path):
    plugin = EddblinkImportPlugin(_make_tdb(tmp_path), _make_tdenv(tmp_path))
    payload = {'version': 1, 'files': {'Item.csv': {'etag': 'abc'}}}
    
    plugin._save_eddblink_state(payload)
    
    state_path = plugin._eddblink_state_path()
    assert state_path.exists()
    assert json.loads(state_path.read_text(encoding='utf-8')) == payload

def test_spansh_init_normalizes_listener_mode_and_log_interval(tmp_path):
    plugin = SpanshImportPlugin(
        _make_tdb(tmp_path),
        _make_tdenv(tmp_path, plugin_options=['listener_mode=YES', 'log_interval=0'])
    )
    
    assert plugin._listener_mode is True
    assert plugin._listener_log_interval == 1
    
    fallback = SpanshImportPlugin(
        _make_tdb(tmp_path / 'fallback'),
        _make_tdenv(tmp_path / 'fallback', plugin_options=['listener_mode=no', 'log_interval=banana'])
    )
    
    assert fallback._listener_mode is False
    assert fallback._listener_log_interval == 30

def test_spansh_trace_is_noop_when_disabled_and_writes_jsonl_when_enabled(tmp_path):
    disabled = SpanshImportPlugin(_make_tdb(tmp_path), _make_tdenv(tmp_path))
    disabled._trace(phase='noop', decision='skip')
    assert not (Path(disabled.tmp_dir) / 'spansh_trace.jsonl').exists()
    
    enabled_root = tmp_path / 'enabled'
    enabled = SpanshImportPlugin(
        _make_tdb(enabled_root),
        _make_tdenv(enabled_root, plugin_options=['debug_trace=1'])
    )
    enabled._trace(phase='system', decision='process', name='Sol')
    if enabled._trace_fp is not None:
        enabled._trace_fp.close()
    
    trace_path = Path(enabled.tmp_dir) / 'spansh_trace.jsonl'
    assert trace_path.exists()
    payload = json.loads(trace_path.read_text(encoding='utf-8').strip())
    assert payload['phase'] == 'system'
    assert payload['decision'] == 'process'
    assert payload['name'] == 'Sol'
