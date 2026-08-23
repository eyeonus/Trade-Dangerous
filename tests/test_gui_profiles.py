import json

from tradedangerous.guiapp.profiles import (
    CommandDraft,
    GuiStore,
    load_gui_store,
    make_profile_id,
    save_gui_store,
)


def test_guistore_default_data_mode_is_unset():
    assert GuiStore.default().data_mode is None


def test_existing_state_without_data_mode_loads_as_crowdsourced(tmp_path):
    payload = GuiStore.default().to_dict()
    payload.pop('data_mode')
    path = tmp_path / 'gui-state.json'
    path.write_text(json.dumps(payload), encoding='utf-8')

    loaded = load_gui_store(path)

    assert loaded.data_mode == 'crowdsourced'


def test_explicit_data_modes_round_trip(tmp_path):
    for data_mode in ('crowdsourced', 'solo'):
        store = GuiStore.default()
        store.data_mode = data_mode
        path = tmp_path / f'{data_mode}-gui-state.json'

        save_gui_store(store, path)
        loaded = load_gui_store(path)

        assert loaded.data_mode == data_mode

def test_make_profile_id_slugifies_and_deduplicates():
    existing = {'cobra-mk-iii', 'cobra-mk-iii-2'}
    
    profile_id = make_profile_id(' Cobra Mk. III ', existing)
    
    assert profile_id == 'cobra-mk-iii-3'

def test_guistore_ensure_defaults_repairs_partial_state():
    store = GuiStore(
        selected_profile_id='missing',
        selected_command='',
        profiles=[],
        drafts={},
    )
    
    store.ensure_defaults()
    
    assert store.selected_profile_id == 'ship-1'
    assert store.selected_command == 'run'
    assert store.profiles[0].profile_id == 'ship-1'
    assert 'run' in store.drafts
    assert isinstance(store.drafts['run'], CommandDraft)

def test_save_and_load_gui_store_round_trip(tmp_path):
    store = GuiStore.default()
    store.launcher_port = 8123
    store.global_settings.commander_name = 'Commander Test'
    store.drafts['trade'] = CommandDraft(main_values={'origin': 'Sol/Abraham Lincoln'})
    path = tmp_path / 'gui-state.json'
    
    save_gui_store(store, path)
    loaded = load_gui_store(path)
    
    assert loaded.launcher_port == 8123
    assert loaded.global_settings.commander_name == 'Commander Test'
    assert loaded.drafts['trade'].main_values['origin'] == 'Sol/Abraham Lincoln'
