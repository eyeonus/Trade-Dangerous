"""Read commander and current-ship facts from the Elite Dangerous journal.

This is a GUI-only convenience: it reuses TD's existing journal reader
(`EliteGame`) to pull a handful of *current* facts for pre-filling the
left-pane commander and ship-profile fields. It performs no ship-performance
maths and changes no CLI behaviour.

Journal field names are per Frontier's Player Journal manual and were verified
against a live journal: the latest `Loadout`/`LoadGame` events carry `Ship`,
`ShipName`, `ShipIdent`, `CargoCapacity`, `Rebuy` and `Credits`; the commander
name comes through `EliteGame.get_status()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tradedangerous.tradeenv import TradeEnv
from tradedangerous.tradegame import EliteGame, JournalLoad

# Events that describe the ship you are currently in and your balance. We scan
# the loaded journal and let the most recent occurrence win, mirroring how
# EliteGame.get_status() folds events together.
_SHIP_EVENTS = ('LoadGame', 'Loadout')
_SHIP_KEYS = ('Ship', 'ShipName', 'ShipIdent', 'CargoCapacity', 'Rebuy',
              'Credits')

@dataclass(slots=True)
class JournalFacts:
    """Facts pulled from the journal. Any field may be None when absent."""

    commander_name: str | None = None
    credits: int | None = None
    cargo_capacity: int | None = None
    insurance: int | None = None        # sourced from the ship's Rebuy cost
    ship_name: str | None = None        # player ShipName, else ident, else type
    ship_type: str | None = None        # internal type symbol, e.g. 'explorer_nx'
    ship_ident: str | None = None
    # Field labels that were populated, for a clear "what was imported" report.
    filled: list[str] = field(default_factory=list)

def read_journal_facts(journal_dir: str | None) -> JournalFacts:
    """Load the most recent journal and extract current commander/ship facts.

    `journal_dir` blank/None leaves discovery to TD's normal lookup
    (ELITE_JOURNAL_PATH, then the OS default). A missing or undiscoverable
    folder raises TradeException (GameFolderError), which the caller surfaces.
    """
    tdenv = TradeEnv()
    if journal_dir:
        # journal_path() honours tdenv.journal_path ahead of the env var and
        # OS default -- the same override the GUI uses for command execution.
        tdenv.journal_path = journal_dir

    # Journal events alone carry everything we need, so skip the JSON sidecar
    # files: that keeps the import working even if Status.json / ModulesInfo
    # are missing or locked while the game is writing them.
    game = EliteGame(
        tdenv=tdenv,
        journal_load=JournalLoad.MOST_RECENT,
        json_files=[],
    )

    status = game.get_status()
    facts = JournalFacts()
    facts.commander_name = _clean(status.commander)
    facts.cargo_capacity = _int(status.cargo_space)

    # get_status() does not surface credits, rebuy or ship identity, so collect
    # those from the most recent LoadGame/Loadout events directly.
    latest: dict[str, object] = {}
    for event in game.journal:
        if event.get('event') in _SHIP_EVENTS:
            for key in _SHIP_KEYS:
                value = event.get(key)
                if value not in (None, ''):
                    latest[key] = value

    facts.credits = _int(latest.get('Credits'))
    facts.insurance = _int(latest.get('Rebuy'))
    facts.ship_type = _clean(latest.get('Ship'))
    facts.ship_ident = _clean(latest.get('ShipIdent'))
    # The profile has a single name field; prefer the player's ship name, then
    # its ID string, then the raw type symbol.
    facts.ship_name = (_clean(latest.get('ShipName'))
                       or facts.ship_ident
                       or facts.ship_type)
    if facts.cargo_capacity is None:
        facts.cargo_capacity = _int(latest.get('CargoCapacity'))

    facts.filled = _label_filled(facts)
    return facts

def _label_filled(facts: JournalFacts) -> list[str]:
    labels: list[str] = []
    if facts.commander_name is not None:
        labels.append('Commander Name')
    if facts.credits is not None:
        labels.append('Credits')
    if facts.ship_name is not None:
        labels.append('Ship Name')
    if facts.cargo_capacity is not None:
        labels.append('Capacity')
    if facts.insurance is not None:
        labels.append('Insurance')
    return labels

def _clean(value: object) -> str | None:
    text = str(value).strip() if value is not None else ''
    return text or None

def _int(value: object) -> int | None:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
