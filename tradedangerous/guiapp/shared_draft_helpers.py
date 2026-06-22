"""Shared draft mutation helpers for command workspaces."""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

class DraftValueHelper:
    """Provide consistent widget-to-draft update semantics across workspaces."""
    
    def _set_text(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        cleaned = str(value or '').strip()
        if cleaned == '':
            payload.pop(key, None)
        else:
            payload[key] = cleaned
        self.on_changed()
    
    def _set_int(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
        label: str,
    ) -> None:
        if value is None or value == '':
            payload.pop(key, None)
            self.on_changed()
            return
        
        if isinstance(value, float):
            # NiceGUI number inputs may hand back integral values as floats.
            # Accept 5.0 for integer-only fields, but reject fractional input.
            if value.is_integer():
                payload[key] = int(value)
                self.on_changed()
                return
            ui.notify(f'{label} must be an integer.', color='negative')
            return
        
        if isinstance(value, int):
            payload[key] = value
            self.on_changed()
            return
        
        ui.notify(f'{label} must be an integer.', color='negative')
    
    def _set_float(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        if value is None or value == '':
            payload.pop(key, None)
        else:
            payload[key] = value
        self.on_changed()
    
    def _set_bool(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        payload[key] = bool(value)
        self.on_changed()
    
    def _set_tri_state(
        self,
        payload: dict[str, Any],
        key: str,
        value: Any,
    ) -> None:
        cleaned = str(value or '')
        if cleaned == '':
            # Blank means "Any", which is represented by omitting the flag.
            payload.pop(key, None)
        else:
            payload[key] = cleaned
        self.on_changed()
    
    def _set_pad_size_flag(self, pad_size: str, enabled: Any) -> None:
        current_raw = self.draft.main_values.get('padSize')
        current = set('SML') if current_raw in (None, '') else set(str(current_raw))
        
        if enabled:
            current.add(pad_size)
        else:
            current.discard(pad_size)
        
        ordered = ''.join(size for size in 'SML' if size in current)
        if ordered == 'SML':
            # The CLI treats a missing pad-size option as unrestricted.
            self.draft.main_values.pop('padSize', None)
        else:
            self.draft.main_values['padSize'] = ordered
        
        self.on_changed()
    
    @staticmethod
    def _split_station_pair_value(value: Any) -> tuple[str, str]:
        text = str(value or '').strip()
        if '/' not in text:
            return text, ''
        system_name, station_name = text.split('/', 1)
        return system_name.strip(), station_name.strip()
    
    def _station_pair_values(
        self,
        payload: dict[str, Any],
        *,
        system_key: str,
        station_key: str,
        combined_key: str,
    ) -> tuple[str, str]:
        system_name = self._text_value(payload, system_key).strip()
        station_name = self._text_value(payload, station_key).strip()
        
        if system_name or station_name:
            return system_name, station_name
        
        return self._split_station_pair_value(payload.get(combined_key))
    
    def _sync_station_pair_value(
        self,
        payload: dict[str, Any],
        *,
        system_key: str,
        station_key: str,
        combined_key: str,
        allow_bare_system: bool = False,
    ) -> None:
        system_name = self._text_value(payload, system_key).strip()
        station_name = self._text_value(payload, station_key).strip()
        
        if system_name and station_name:
            payload[combined_key] = f'{system_name}/{station_name}'
        elif system_name and allow_bare_system:
            # Direct accepts a bare system (all qualifying stations). Other
            # callers (e.g. market) still require a station, so this is opt-in.
            payload[combined_key] = system_name
        else:
            payload.pop(combined_key, None)
    
    def _normalize_station_pair_value(
        self,
        payload: dict[str, Any],
        *,
        system_key: str,
        station_key: str,
        combined_key: str,
        allow_bare_system: bool = False,
    ) -> tuple[str, str]:
        system_name = self._text_value(payload, system_key).strip()
        station_name = self._text_value(payload, station_key).strip()
        combined_system, combined_station = self._split_station_pair_value(
            payload.get(combined_key)
        )
        
        if not system_name and combined_system:
            system_name = combined_system
            payload[system_key] = combined_system
        
        if not station_name and combined_station:
            station_name = combined_station
            payload[station_key] = combined_station
        
        self._sync_station_pair_value(
            payload,
            system_key=system_key,
            station_key=station_key,
            combined_key=combined_key,
            allow_bare_system=allow_bare_system,
        )
        return system_name, station_name
    
    @staticmethod
    def _resolve_suggestion_id(
        text: str | None,
        *,
        resolver: Callable[[str], Any] | None,
        id_attr: str,
    ) -> int | None:
        cleaned = str(text or '').strip()
        if cleaned == '':
            return None
        if resolver is None:
            return None
        
        suggestion = resolver(cleaned)
        if suggestion is None:
            return None
        
        value = getattr(suggestion, id_attr, None)
        if value is None:
            return None
        return int(value)
    
    @staticmethod
    def _text_value(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        return '' if value is None else str(value)
    
    @staticmethod
    def _number_value(payload: dict[str, Any], key: str) -> int | float | None:
        value = payload.get(key)
        if value in (None, ''):
            return None
        return value
    
    @staticmethod
    def _bool_value(payload: dict[str, Any], key: str) -> bool:
        return bool(payload.get(key))
    
    @staticmethod
    def _tri_state_value(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if value in ('Y', 'N', '?'):
            return value
        return ''
    
    def _pad_size_enabled(self, pad_size: str) -> bool:
        current = self.draft.main_values.get('padSize')
        if current in (None, ''):
            return True
        return pad_size in str(current)
