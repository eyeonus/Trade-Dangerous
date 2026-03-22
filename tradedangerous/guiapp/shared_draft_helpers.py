"""Shared draft mutation helpers for command workspaces."""

from __future__ import annotations

from typing import Any

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
