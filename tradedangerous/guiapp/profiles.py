"""Persistence helpers for GUI-only state stored outside the main TD config."""

from __future__ import annotations

import configparser
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tradedangerous.db.paths import resolve_data_dir, resolve_db_config_path

GUI_STATE_FILENAME = 'tradegui_state.json'
SCHEMA_VERSION = 1
LAUNCHER_PORT_MIN = 8000
LAUNCHER_PORT_MAX = 8999
_IMPORT_TRANSIENT_FLAGS = frozenset({
    'all',
    'skipvend',
    'clean',
    'optimize',
    'force',
})


def _serialize_command_draft(command: str, draft: 'CommandDraft') -> dict[str, Any]:
    payload = draft.to_dict()
    if command == 'import':
        payload['main_values'] = {
            key: value
            for key, value in payload['main_values'].items()
            if key not in _IMPORT_TRANSIENT_FLAGS
        }
    return payload


def _coerce_launcher_port(value: Any) -> int | None:
    if value in {None, ''}:
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if port < LAUNCHER_PORT_MIN or port > LAUNCHER_PORT_MAX:
        return None
    return port

@dataclass(slots=True)
class GlobalSettings:
    """Persisted commander-wide defaults shown in the left pane."""
    
    commander_name: str | None = None
    credits: int | None = None
    max_data_age_days: float | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> 'GlobalSettings':
        data = data or {}
        return cls(
            commander_name=data.get('commander_name'),
            credits=data.get('credits'),
            max_data_age_days=data.get('max_data_age_days'),
        )
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class ShipProfile:
    """Persisted ship baseline editable from the shell's profile section."""
    
    profile_id: str
    ship_name: str | None = None
    capacity: int | None = None
    reserved_capacity: int | None = None
    insurance: int | None = None
    jump_range_full_ly: float | None = None
    jump_range_empty_ly: float | None = None
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ShipProfile':
        return cls(
            profile_id=str(data['profile_id']),
            ship_name=data.get('ship_name'),
            capacity=data.get('capacity'),
            reserved_capacity=data.get('reserved_capacity'),
            insurance=data.get('insurance'),
            jump_range_full_ly=data.get('jump_range_full_ly'),
            jump_range_empty_ly=data.get('jump_range_empty_ly'),
        )
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class CommandDraft:
    """Per-command GUI state split into main, advanced, and context fields.
    
    `main_values` backs the always-visible controls, `advanced_values` stores
    dialog-only options, and `context_overrides` stamps left-pane baselines into
    commands such as `run`.
    """
    
    main_values: dict[str, Any] = field(default_factory=dict)
    advanced_values: dict[str, Any] = field(default_factory=dict)
    context_overrides: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> 'CommandDraft':
        data = data or {}
        return cls(
            main_values=dict(data.get('main_values') or {}),
            advanced_values=dict(data.get('advanced_values') or {}),
            context_overrides=dict(data.get('context_overrides') or {}),
        )
    
    def to_dict(self) -> dict[str, Any]:
        return {
            'main_values': dict(self.main_values),
            'advanced_values': dict(self.advanced_values),
            'context_overrides': dict(self.context_overrides),
        }

@dataclass(slots=True)
class GuiStore:
    """Persisted GUI state loaded from and saved to the JSON sidecar file."""
    
    schema_version: int = SCHEMA_VERSION
    launcher_port: int | None = None
    # Optional override for the Elite Dangerous journal directory. Blank/None
    # means "auto", preserving the CLI's normal env-var/OS-default discovery.
    journal_dir: str | None = None
    selected_profile_id: str | None = None
    selected_command: str = 'run'
    global_settings: GlobalSettings = field(default_factory=GlobalSettings)
    profiles: list[ShipProfile] = field(default_factory=list)
    drafts: dict[str, CommandDraft] = field(default_factory=dict)
    layout: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def default(cls) -> 'GuiStore':
        # Seed first-run state with one usable profile and a run draft so the
        # shell never boots into an empty or half-configured workspace.
        default_profile = ShipProfile(
            profile_id='ship-1',
            ship_name='Ship 1',
        )
        return cls(
            selected_profile_id=default_profile.profile_id,
            selected_command='run',
            profiles=[default_profile],
            drafts={'run': CommandDraft()},
            layout={'theme': 'elite'},
        )
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'GuiStore':
        store = cls(
            schema_version=int(data.get('schema_version') or SCHEMA_VERSION),
            launcher_port=_coerce_launcher_port(data.get('launcher_port')),
            journal_dir=(data.get('journal_dir') or None),
            selected_profile_id=data.get('selected_profile_id'),
            selected_command=data.get('selected_command') or 'run',
            global_settings=GlobalSettings.from_dict(data.get('global')),
            profiles=[
                ShipProfile.from_dict(item)
                for item in list(data.get('profiles') or [])
            ],
            drafts={
                command: CommandDraft.from_dict(draft)
                for command, draft in dict(data.get('drafts') or {}).items()
            },
            layout=dict(data.get('layout') or {}),
        )
        store.ensure_defaults()
        return store
    
    def to_dict(self) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'launcher_port': self.launcher_port,
            'journal_dir': self.journal_dir,
            'selected_profile_id': self.selected_profile_id,
            'selected_command': self.selected_command,
            'global': self.global_settings.to_dict(),
            'profiles': [profile.to_dict() for profile in self.profiles],
            'drafts': {
                command: _serialize_command_draft(command, draft)
                for command, draft in self.drafts.items()
            },
            'layout': dict(self.layout),
        }
    
    def ensure_defaults(self) -> None:
        # State files may be missing pieces after upgrades or partial writes.
        # Repair them in memory so the GUI can always boot into a usable state.
        if not self.profiles:
            default_store = self.default()
            self.selected_profile_id = default_store.selected_profile_id
            self.profiles = default_store.profiles
        
        if (
            self.selected_profile_id is None
            or self.get_profile(self.selected_profile_id) is None
        ):
            self.selected_profile_id = self.profiles[0].profile_id
        
        if self.selected_command == '':
            self.selected_command = 'run'
        
        if (
            self.selected_command != 'settings'
            and self.selected_command not in self.drafts
        ):
            self.drafts[self.selected_command] = CommandDraft()
        
        run_draft = self.drafts.get('run')
        if run_draft is not None:
            # Temporary compatibility bridge for older GUI state files.
            # Insurance used to live in run advanced_values; move it into
            # context_overrides so it appears in the main Run Overrides area.
            legacy_insurance = run_draft.advanced_values.pop('insurance', None)
            if (
                legacy_insurance not in (None, '')
                and run_draft.context_overrides.get('insurance') in (None, '')
            ):
                run_draft.context_overrides['insurance'] = legacy_insurance
    
    def get_profile(self, profile_id: str | None) -> ShipProfile | None:
        if profile_id is None:
            return None
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        return None
    
    def require_profile(self, profile_id: str | None) -> ShipProfile:
        profile = self.get_profile(profile_id)
        if profile is None:
            raise KeyError(f'Unknown ship profile: {profile_id!r}')
        return profile
    
    def upsert_profile(self, profile: ShipProfile) -> None:
        for index, current in enumerate(self.profiles):
            if current.profile_id == profile.profile_id:
                self.profiles[index] = profile
                break
        else:
            self.profiles.append(profile)
        self.selected_profile_id = profile.profile_id
    
    def get_or_create_draft(self, command: str) -> CommandDraft:
        draft = self.drafts.get(command)
        if draft is None:
            draft = CommandDraft()
            self.drafts[command] = draft
        return draft
    
    def create_profile(
        self,
        base: ShipProfile | None = None,
        ship_name: str | None = None,
    ) -> ShipProfile:
        profile_name = ship_name or (base.ship_name if base else None) or 'Ship'
        profile_id = make_profile_id(profile_name, self.existing_profile_ids())
        profile = ShipProfile(
            profile_id=profile_id,
            ship_name=ship_name or (base.ship_name if base else profile_name),
            capacity=base.capacity if base else None,
            reserved_capacity=base.reserved_capacity if base else None,
            insurance=base.insurance if base else None,
            jump_range_full_ly=base.jump_range_full_ly if base else None,
            jump_range_empty_ly=base.jump_range_empty_ly if base else None,
        )
        self.upsert_profile(profile)
        return profile
    
    def existing_profile_ids(self) -> set[str]:
        return {profile.profile_id for profile in self.profiles}

def make_profile_id(name: str | None, existing_ids: set[str]) -> str:
    """Slugify a profile name and append a numeric suffix when needed."""
    
    base = re.sub(r'[^a-z0-9]+', '-', (name or 'ship').strip().lower())
    base = base.strip('-') or 'ship'
    candidate = base
    suffix = 2
    while candidate in existing_ids:
        candidate = f'{base}-{suffix}'
        suffix += 1
    return candidate

def _read_db_config() -> configparser.ConfigParser | None:
    cfg_path = resolve_db_config_path()
    if not cfg_path.exists():
        return None
    
    cfg = configparser.ConfigParser()
    cfg.read(cfg_path, encoding='utf-8')
    return cfg

def resolve_gui_state_path() -> Path:
    """Store GUI state alongside the normal Trade Dangerous data files."""
    
    cfg = _read_db_config()
    data_dir = resolve_data_dir(cfg)
    return data_dir / GUI_STATE_FILENAME

def load_gui_store(path: Path | None = None) -> GuiStore:
    """Load the persisted GUI store, or synthesize defaults on first run."""
    
    store_path = path or resolve_gui_state_path()
    if not store_path.exists():
        return GuiStore.default()
    
    try:
        payload = json.loads(store_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f'Invalid GUI state JSON in {store_path}'
        ) from exc
    
    return GuiStore.from_dict(payload)

def save_gui_store(store: GuiStore, path: Path | None = None) -> Path:
    """Write the current GUI store back to disk and return the target path."""
    
    store_path = path or resolve_gui_state_path()
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(
        json.dumps(store.to_dict(), indent=2, sort_keys=False) + '\n',
        encoding='utf-8',
    )
    return store_path
