from tradedangerous.guiapp.import_runtime import consume_one_shot_import_flags
from tradedangerous.guiapp.profiles import CommandDraft, GuiStore
from tradedangerous.guiapp.session import SessionState

def test_import_open_applies_defaults_and_clears_transient_flags():
    store = GuiStore.default()
    store.selected_command = 'import'
    store.drafts['import'] = CommandDraft(
        main_values={
            'solo': True,
            'clean': True,
            'optimize': True,
            'force': True,
        }
    )
    
    session = SessionState.from_store(store)
    
    assert session.draft.main_values['all'] is True
    assert session.draft.main_values['skipvend'] is True
    assert 'clean' not in session.draft.main_values
    assert 'optimize' not in session.draft.main_values
    assert 'force' not in session.draft.main_values
    assert session.draft.main_values['solo'] is True

def test_import_open_reapplies_defaults_each_time_it_is_selected():
    store = GuiStore.default()
    store.drafts['import'] = CommandDraft(main_values={'solo': True})
    session = SessionState.from_store(store)
    
    session.set_command(store, 'import')
    session.draft.main_values.pop('all', None)
    session.draft.main_values.pop('skipvend', None)
    session.draft.main_values['clean'] = True
    session.draft.main_values['force'] = True
    
    session.set_command(store, 'run')
    session.set_command(store, 'import')
    
    assert session.draft.main_values['all'] is True
    assert session.draft.main_values['skipvend'] is True
    assert 'clean' not in session.draft.main_values
    assert 'force' not in session.draft.main_values
    assert session.draft.main_values['solo'] is True

def test_import_transient_flags_are_not_serialized():
    store = GuiStore.default()
    store.drafts['import'] = CommandDraft(
        main_values={
            'all': True,
            'skipvend': True,
            'clean': True,
            'optimize': True,
            'force': True,
            'solo': True,
            '7days': True,
        }
    )
    
    payload = store.to_dict()
    main_values = payload['drafts']['import']['main_values']
    
    assert 'all' not in main_values
    assert 'skipvend' not in main_values
    assert 'clean' not in main_values
    assert 'optimize' not in main_values
    assert 'force' not in main_values
    assert main_values['solo'] is True
    assert main_values['7days'] is True

def test_consume_one_shot_import_flags_clears_force_as_well():
    draft = CommandDraft(
        main_values={
            'clean': True,
            'optimize': True,
            'force': True,
            'solo': True,
        }
    )
    
    changed = consume_one_shot_import_flags(draft=draft)
    
    assert changed is True
    assert 'clean' not in draft.main_values
    assert 'optimize' not in draft.main_values
    assert 'force' not in draft.main_values
    assert draft.main_values['solo'] is True
