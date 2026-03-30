"""Mutable session state for the GUI, separate from the persisted store."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .profiles import CommandDraft, GlobalSettings, GuiStore, ShipProfile

class ExecutionStatus(str, Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'

@dataclass(slots=True)
class WorkingGlobalState:
    commander_name: str | None = None
    credits: int | None = None
    max_data_age_days: float | None = None
    
    @classmethod
    def from_saved(cls, settings: GlobalSettings) -> 'WorkingGlobalState':
        return cls(
            commander_name=settings.commander_name,
            credits=settings.credits,
            max_data_age_days=settings.max_data_age_days,
        )
    
    def as_saved(self) -> GlobalSettings:
        return GlobalSettings(
            commander_name=self.commander_name,
            credits=self.credits,
            max_data_age_days=self.max_data_age_days,
        )

@dataclass(slots=True)
class WorkingShipProfileState:
    """Editable copy of the selected ship profile.
    
    `is_dirty` tracks unsaved left-pane edits and is never persisted.
    """
    
    profile_id: str | None = None
    ship_name: str | None = None
    capacity: int | None = None
    reserved_capacity: int | None = None
    jump_range_full_ly: float | None = None
    jump_range_empty_ly: float | None = None
    is_dirty: bool = False
    
    @classmethod
    def from_saved(cls, profile: ShipProfile) -> 'WorkingShipProfileState':
        return cls(
            profile_id=profile.profile_id,
            ship_name=profile.ship_name,
            capacity=profile.capacity,
            reserved_capacity=profile.reserved_capacity,
            jump_range_full_ly=profile.jump_range_full_ly,
            jump_range_empty_ly=profile.jump_range_empty_ly,
            is_dirty=False,
        )
    
    def as_saved(self) -> ShipProfile:
        if self.profile_id is None:
            raise ValueError('Working ship profile has no profile_id.')
        return ShipProfile(
            profile_id=self.profile_id,
            ship_name=self.ship_name,
            capacity=self.capacity,
            reserved_capacity=self.reserved_capacity,
            jump_range_full_ly=self.jump_range_full_ly,
            jump_range_empty_ly=self.jump_range_empty_ly,
        )
    
    @property
    def effective_capacity(self) -> int | None:
        if self.capacity is None:
            return None
        if self.reserved_capacity is None:
            return self.capacity
        if self.reserved_capacity > self.capacity:
            return None
        return self.capacity - self.reserved_capacity

@dataclass(slots=True)
class ExecutionState:
    """Last command result plus import-specific live progress fields."""
    
    status: ExecutionStatus = ExecutionStatus.IDLE
    active_command: str | None = None
    error_message: str | None = None
    raw_output: str = ''
    diagnostics_output: str = ''
    # Structured output for the right pane. This may now be either the original
    # in-process adapter payload or a plain subprocess-safe snapshot.
    structured_result: Any = None
    import_log_lines: list[str] = field(default_factory=list)
    import_status_text: str = ''
    import_parent_label: str | None = None
    import_parent_value: int | None = None
    import_parent_total: int | None = None
    import_child_label: str | None = None
    import_child_value: int | None = None
    import_child_total: int | None = None
    import_stop_requested: bool = False
    import_stop_confirming: bool = False

@dataclass(slots=True)
class SessionState:
    """Live working state for a single GUI session."""
    
    selected_command: str = 'run'
    selected_profile_id: str | None = None
    global_state: WorkingGlobalState = field(default_factory=WorkingGlobalState)
    ship_state: WorkingShipProfileState = field(
        default_factory=WorkingShipProfileState
    )
    draft: CommandDraft = field(default_factory=CommandDraft)
    execution: ExecutionState = field(default_factory=ExecutionState)
    # Live import worker handle while an import is running. This is transient UI state.
    active_import_runner: Any = None
    
    @classmethod
    def from_store(cls, store: GuiStore) -> 'SessionState':
        store.ensure_defaults()
        profile = store.require_profile(store.selected_profile_id)
        if store.selected_command == 'settings':
            # Settings is a GUI-only workspace, so it does not reuse a command
            # draft intended for CLI-backed execution.
            draft = CommandDraft()
        else:
            # SessionState is the mutable working copy. GuiStore remains the
            # persisted snapshot on disk until explicit saves happen.
            draft = store.get_or_create_draft(store.selected_command)
            cls._normalize_command_draft(store.selected_command, draft)
        return cls(
            selected_command=store.selected_command,
            selected_profile_id=store.selected_profile_id,
            global_state=WorkingGlobalState.from_saved(store.global_settings),
            ship_state=WorkingShipProfileState.from_saved(profile),
            draft=draft,
        )
    
    def set_command(self, store: GuiStore, command: str) -> None:
        self.selected_command = command
        store.selected_command = command
        if command == 'settings':
            self.draft = CommandDraft()
            return
        self.draft = store.get_or_create_draft(command)
        self._normalize_command_draft(command, self.draft)
    
    @staticmethod
    def _normalize_command_draft(command: str, draft: CommandDraft) -> None:
        if command == 'import':
            # Import always opens in the safe fast-path mode unless the user
            # explicitly opts into heavier work for the current visit.
            draft.main_values['all'] = True
            draft.main_values['skipvend'] = True
            for key in ('clean', 'optimize', 'force'):
                draft.main_values.pop(key, None)
    
    def set_global_state(
        self,
        store: GuiStore,
        *,
        commander_name: str | None,
        credits: int | None,
        max_data_age_days: float | None,
    ) -> None:
        self.global_state = WorkingGlobalState(
            commander_name=commander_name,
            credits=credits,
            max_data_age_days=max_data_age_days,
        )
        store.global_settings = self.global_state.as_saved()
    
    def load_profile(self, store: GuiStore, profile_id: str) -> None:
        profile = store.require_profile(profile_id)
        self.selected_profile_id = profile.profile_id
        store.selected_profile_id = profile.profile_id
        self.ship_state = WorkingShipProfileState.from_saved(profile)
    
    def save_ship_profile(self, store: GuiStore) -> None:
        saved = self.ship_state.as_saved()
        store.upsert_profile(saved)
        self.selected_profile_id = saved.profile_id
        self.ship_state.is_dirty = False
    
    def revert_ship_profile(self, store: GuiStore) -> None:
        profile = store.require_profile(self.selected_profile_id)
        self.ship_state = WorkingShipProfileState.from_saved(profile)
    
    def create_new_ship_profile(self, store: GuiStore) -> None:
        base = self.ship_state.as_saved()
        created = store.create_profile(base=base)
        self.load_profile(store, created.profile_id)
    
    def mark_ship_dirty(self) -> None:
        self.ship_state.is_dirty = True
    
    def set_execution(
        self,
        *,
        status: ExecutionStatus,
        active_command: str | None = None,
        error_message: str | None = None,
        raw_output: str = '',
        diagnostics_output: str = '',
        structured_result: Any = None,
        import_log_lines: list[str] | None = None,
        import_status_text: str = '',
        import_parent_label: str | None = None,
        import_parent_value: int | None = None,
        import_parent_total: int | None = None,
        import_child_label: str | None = None,
        import_child_value: int | None = None,
        import_child_total: int | None = None,
        import_stop_requested: bool = False,
        import_stop_confirming: bool = False,
    ) -> None:
        # Replace the whole execution object in one step so the right pane never
        # renders a mixture of old and new command state.
        self.execution = ExecutionState(
            status=status,
            active_command=active_command,
            error_message=error_message,
            raw_output=raw_output,
            diagnostics_output=diagnostics_output,
            structured_result=structured_result,
            import_log_lines=list(import_log_lines or []),
            import_status_text=import_status_text,
            import_parent_label=import_parent_label,
            import_parent_value=import_parent_value,
            import_parent_total=import_parent_total,
            import_child_label=import_child_label,
            import_child_value=import_child_value,
            import_child_total=import_child_total,
            import_stop_requested=import_stop_requested,
            import_stop_confirming=import_stop_confirming,
        )
