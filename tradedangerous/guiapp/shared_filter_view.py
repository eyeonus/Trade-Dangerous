"""Reusable filter widgets shared by multiple command workspaces."""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

TRI_STATE_OPTIONS = {
    '': 'Any',
    'Y': 'Yes only',
    'N': 'No only',
    '?': 'Unknown only',
}

def build_shared_filter_section(
    *,
    get_bool: Callable[[str], bool],
    get_tri_state: Callable[[str], str],
    set_bool: Callable[[str, Any], None],
    set_tri_state: Callable[[str, Any], None],
    pad_size_enabled: Callable[[str], bool],
    set_pad_size_flag: Callable[[str, Any], None],
    extra_builder: Callable[[], None] | None = None,
    post_builder: Callable[[], None] | None = None,
) -> None:
    """Render the common TD filter controls via caller-provided getters/setters."""
    
    with ui.card().classes('w-full'):
        ui.label('Common Filters')
        
        with ui.row().classes('w-full gap-3'):
            ui.select(
                TRI_STATE_OPTIONS,
                value=get_tri_state('planetary'),
                label='Planetary',
                on_change=lambda event: set_tri_state(
                    'planetary',
                    event.value,
                ),
            ).classes('w-48').tooltip(
                'Filter by planetary status: Any, Yes only, No only, '
                'or Unknown only.'
            )
            ui.select(
                TRI_STATE_OPTIONS,
                value=get_tri_state('fleet'),
                label='Fleet Carrier',
                on_change=lambda event: set_tri_state(
                    'fleet',
                    event.value,
                ),
            ).classes('w-48').tooltip(
                'Filter by fleet-carrier status: Any, Yes only, No only, '
                'or Unknown only.'
            )
            ui.select(
                TRI_STATE_OPTIONS,
                value=get_tri_state('settlement'),
                label='Settlement',
                on_change=lambda event: set_tri_state(
                    'settlement',
                    event.value,
                ),
            ).classes('w-48').tooltip(
                'Filter by Settlement status: Any, Yes only, No only, '
                'or Unknown only.'
            )
            
            if extra_builder is not None:
                # Some workspaces have one extra control that belongs beside the
                # tri-state selectors rather than in a separate section.
                extra_builder()
        
        # Pad size is tracked as a compact bitset in drafts, but the UI keeps it
        # as three checkboxes because that is far easier to sanity-check.
        with ui.row().classes('w-full items-center gap-4'):
            ui.label('Pad sizes')
            ui.checkbox(
                'S',
                value=pad_size_enabled('S'),
                on_change=lambda event: set_pad_size_flag(
                    'S',
                    event.value,
                ),
            ).tooltip(
                'Allow stations with small pads. All three pad-size boxes '
                'checked means unrestricted.'
            )
            ui.checkbox(
                'M',
                value=pad_size_enabled('M'),
                on_change=lambda event: set_pad_size_flag(
                    'M',
                    event.value,
                ),
            ).tooltip(
                'Allow stations with medium pads. All three pad-size boxes '
                'checked means unrestricted.'
            )
            ui.checkbox(
                'L',
                value=pad_size_enabled('L'),
                on_change=lambda event: set_pad_size_flag(
                    'L',
                    event.value,
                ),
            ).tooltip(
                'Allow stations with large pads. All three pad-size boxes '
                'checked means unrestricted.'
            )
        
        if post_builder is not None:
            # Local and similar commands append their own full-width filters
            # after the shared TD station traits.
            post_builder()
        
        ui.label(
            'All pad sizes checked means unrestricted. '
            'The tri-state filters use Any / Yes / No / Unknown semantics.'
        ).classes('text-sm text-gray-600')
