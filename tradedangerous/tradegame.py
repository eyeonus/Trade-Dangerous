"""
tradegame provides the EliteGame class for accessing game journal data for Elite: Dangerous.

This module provides access to current game state by reading Elite: Dangerous
journal files and real-time status data. It extracts trade-relevant information
such as current location, ship configuration, cargo capacity, and credits.

If the journal is not in a standard place, such as on Linux or SteamDeck,
you can set the environment variable "ELITE_JOURNAL_PATH".

Journal File Format:
    Line-delimited JSON files written to OS-specific saved games directory.
    Each line is a complete JSON object representing a game event.

Supported Data:
    - Commander name and credits
    - Current system and station (if docked)
    - Ship type and configuration
    - Cargo capacity and current cargo mass
    - Jump range (laden and unladen)

Example:
    # Default everything.
    from tradedangerous.tradegame import EliteGame
    
    game = EliteGame()
    print(f"Commander: {game.commander_name}")
    
    
Example:
    # Builder-pattern with "TradeEnv" for arguments.
    from tradedangerous import TradeEnv
    from tradedangerous.tradegame import EliteGame
    
    tdenv = TradeEnv(debug=2, path="/Elite/Saved Games")
    elite = EliteGame(tdenv=tdenv)
    print(f"Current Station: {elite.current_station}")


Example:
    # Control which files are loaded; the same argument names can be
    # set as properties on a tdenv instance instead.
    from tradedangerous.tradegame import EliteGame, JournalLoad as jl, JsonFiles as jf
    elite = EliteGame(
                path="/Elite/Saved Games",
                # journals alternatives: None (don't load), or an integer limit,
                journal_load=jl.ALL_JOURNALS,
                extra_jsons=[jf.Outfitting],
    )
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import datetime
import enum
import os
import re
import time
import typing

import orjson

from .tradeenv import TradeEnv
from .tradeexcept import TradeException

if typing.TYPE_CHECKING:
    from collections.abc import Generator, Iterable
    from typing import Any, Final


# Environment variable to override
ELITE_JOURNAL_ENVVAR = "ELITE_JOURNAL_PATH"


class GameFolderError(TradeException):
    """ GameFolderError indicates we could not find where the saved game data is. """
    def __init__(self, msg: str) -> None:
        super().__init__(
            "Journal functionality needs to know where Elite's save-game data "
            f"is stored, aka the Journal Folder: {msg}. "
            f"Set the '{ELITE_JOURNAL_ENVVAR}' environment variable to the correct path for your machine"
        )


class GameException(TradeException):
    """ GameException is base exception raised when a game file cannot be loaded or parsed."""


class GameDataException(TradeException):
    def __str__(self) -> str:
        return (
            super().__str__() + "\n" +
            "- If you just launched the game, try again after the game has loaded.\n"
            "- If the game is already running, you may need to change screen/dock/undock "
                "for the game to update/generate the file\n"
            f"- Check the journal folder is correct and/or set the {ELITE_JOURNAL_ENVVAR} environment variable\n"
            "- This can happen if the game updates the file just as you run the command; try again"
        )


class JournalException(GameDataException):
    """ JournalException is raised when a journal file cannot be loaded or parsed. """


class JsonException(GameDataException):
    """ JsonException is raised when a JSON file cannot be loaded or parsed. """


class MissingJsonError(JsonException):
    """ MissingJsonError indicates a required JSON file was not present. """
    def __init__(self, msg: str) -> None:
        super().__init__(f"Required save-game json data file was missing: {msg}.\n")


@dataclass
class Status:
    timestamp: str | None = None
    commander: str | None = None
    fid: str | None = None
    star_system: str | None = None
    system_address: int | None = None
    station_name: str | None = None
    station_type: str | None = None
    docked: bool = False
    landed: bool = False
    credits: int | None = None
    destination: dict[str, Any] | None = None
    cargo_space: int | None = None
    cargo_load: int | None = None


@enum.unique
class JournalLoad(enum.IntEnum):
    DO_NOT_LOAD  = 0
    MOST_RECENT  = 1
    ALL_JOURNALS = -1


@enum.unique
class JsonFiles(str, enum.Enum):
    """Enumeration of supported JSON data files."""
    BACKPACK    = "Backpack.json"
    CARGO       = "Cargo.json"
    MARKET      = "Market.json"
    MODULESINFO = "ModulesInfo.json"
    NAVROUTE    = "NavRoute.json"
    OUTFITTING  = "Outfitting.json"
    SHIPLOCKER  = "ShipLocker.json"
    SHIPYARD    = "Shipyard.json"
    STATUS      = "Status.json"


# The format used for timestamps.
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"


# Default journal directory paths by OS
WINDOWS_JOURNAL_DIR: Final[Path]     = Path(Path.home(), "Saved Games", "Frontier Developments", "Elite Dangerous")
MACOS_JOURNAL_DIR: Final[Path]       = Path(Path.home(), "Library", "Application Support", "Frontier Developments", "Elite Dangerous")


@contextmanager
def bench(tdenv: TradeEnv, label: str) -> Generator[None]:
    """ Context manager bench for measuring elapsed time of code blocks. """
    start = time.perf_counter()
    yield
    end = time.perf_counter()
    elapsed = end - start
    tdenv.DEBUG0(f"{label} took {elapsed:.6f} seconds")


class EliteGame:
    """
    EliteGame class reads the various data files Frontier expose for Elite: Dangerous tools
    to access current game state: the journal files and a collection of json files.
    
    By default reads the most recent journal file and DEFAULT_JSON_FILES. Additional files
    can be loaded.
    
    Reads the most recent journal file to extract current game state including
    location, ship configuration, cargo, and credits. Supports both Windows
    and macOS journal locations.

    Interpretation of the data is mostly left to the caller. Some common data can be
    summarized for you by calling get_status().
    
    Example:
        game = EliteGame()
        status = game.get_status()
        if status.docked:
            print(f"Docked at {status.star_system}/{status.station_name}"
        else:
            print(f"In space at {status.star_system}")
    """
    # Class variables/Constants.
    DEFAULT_JOURNAL_LOAD: Final[JournalLoad] = JournalLoad.MOST_RECENT
    DEFAULT_JSON_FILES: Final[list[JsonFiles]] = [
        JsonFiles.STATUS,       # Fairly stock data
        JsonFiles.MODULESINFO,  # So we can determine your cargo capacity
    ]
    
    # Member variables.
    tdenv: TradeEnv                             # context object we're associated with
    path: Path                                  # Elite's save-game folder
    journal_load: JournalLoad                   # journal files we want to load
    json_files: list[JsonFiles]                 # json files we want to load
    
    # Loaded data.
    journals_loaded: list[Path]                 # json files we've loaded or empty
    journal: list[dict[str, dict]]              # events in load order (oldest->newest)
    history:  dict[str, list[dict[str, dict]]]  # oldest-first history per event name
    events: dict[str, dict[str, Any]]           # most-recent only instance of each event
    
    jsons_loaded: list[JsonFiles]               # files actually loaded
    json_data: dict[JsonFiles, dict[str, Any]]  # json file -> the data we loaded
    
    loaded_time: datetime.datetime              # when the load was completed
    
    status: Status | None                       # cache results from get_status()
    
    def __init__(
        self,
        *,
        tdenv: TradeEnv | None = None,
        path: str | Path | None = None,              # platform specific default
        journal_load: JournalLoad | None = None,     # default: EliteGame.DEFAULT_JOURNAL_LOAD
        json_files: list[JsonFiles] | None = None,   # default: EliteGame.DEFAULT_JSON_FILES
        extra_jsons: list[JsonFiles] | None = None,  # default: []
    ) -> None:
        """
            Initialize EliteGame instance by reading journal and JSON files.
            
            :param tdenv:        Optional TradeEnv instance for parameters, configuration, logging, etc.
                                 If path, journal_load, and/or json_files are not provided,
                                 tdenv will be used for defaults before falling back to the class defaults.
            :param path:         Optional path to Elite: Dangerous saved games directory.
                                 If not provided, uses tdenv.journal_path or discovers default based on OS.
            :param journal_load: Optional JournalLoad enum to control if/how many journals
                                 are loaded. If an integer value is provided, it indicates the
                                 maximum number of journals (most recent first) to load.
                                 If None, uses tdenv or class default.
            :param json_files:   Optional list of JsonFiles enum values indicating
                                   which JSON files to load. If None, uses tdenv or class default.
        """
        self.tdenv = tdenv or TradeEnv()
        self.journals_loaded = []
        self.journal = []
        self.history = {}
        self.events = {}
        self.jsons_loaded = []
        self.json_data = {}
        self.status = None
        
        # Populate the options in reverse order of priority: default, tdenv, explicit parameter.
        self.path = journal_path(self.tdenv, path)
        self.tdenv.DEBUG0("elite journal path: {}", self.path)
        
        self.journal_load = self.DEFAULT_JOURNAL_LOAD
        if tdenv and (env_journal_load := getattr(tdenv, "journal_load", None)):
            self.journal_load = env_journal_load
        if journal_load is not None:
            self.journal_load = journal_load
        self.tdenv.DEBUG1("elite game journal load: {!r}", self.journal_load)
        
        self.json_files = self.DEFAULT_JSON_FILES.copy()
        if tdenv and (env_json_files := getattr(tdenv, "journal_json_files", None)) is not None:
            self.json_files = env_json_files
        if json_files is not None:  # explicit None check so that passing `json_files=[]` works.
            self.json_files = json_files
        
        if tdenv and (env_extra_jsons := getattr(tdenv, "journal_extra_jsons", None)) is not None:
            self.json_files.extend(env_extra_jsons)
        if extra_jsons:
            self.json_files.extend(extra_jsons)
        
        self.json_files = list(set(self.json_files))  # deduplicate
        self.tdenv.DEBUG1("elite game json files: {!r}", self.json_files)

        # self.loaded_time is set on completion of self.refresh()
        
        with bench(self.tdenv, "EliteGame refresh"):
            self.refresh()
    
    def list_journals(self) -> list[Path]:
        """ Returns a list of journals with the most recent first, if any are present in the journal path. """
        journals: dict[Path, str] = {}
        candidates: list[Path] = list(self.path.glob("Journal.*.log"))  # otherwise it's a generator

        self.tdenv.DEBUG3("available: {}", candidates)
        for journal_file in candidates:
            # It's expected to have YYYY'-'MM'-'DD'T'HHMMSS'.'LOGN'.log',
            # which forms a nice simple collation order number/string
            index = re.match(r"Journal\.(\d{4})-(\d{2})-(\d{2})T(\d{6})\.(\d+)\.log$", journal_file.name)
            if not index:
                self.tdenv.DEBUG2("ignoring {}, doesn't match our guard pattern", journal_file)
                continue  # ignore, no match
            
            self.tdenv.DEBUG3("considering {}", journal_file)
            journals[journal_file] = "".join(index.groups())
        
        return sorted(journals.keys(), key=lambda file: journals[file], reverse=True)
    
    def refresh(self) -> None:
        """
        Refresh game state by re-reading journal and status files.
        
        Call this method to update state after game events occur. Useful
        when polling for changes in a long-running application.
        """
        self.tdenv.DEBUG1("Refreshing game state")
        self.status = None
        with bench(self.tdenv, "_load_journals"):
            self._load_journals()
        with bench(self.tdenv, "_load_json_files"):
            self._load_json_files()
        self.loaded_time = datetime.datetime.now()
    
    def _load_journals(self) -> None:
        """
            @internal _load_journals will apply self.journal_load and
            attempt to have the appropriate journal files loaded.
            
            If self.journal_load is DO_NOT_LOAD, no files are loaded and existing
            data is cleared. If MOST_RECENT, only the most recent journal is
            loaded. If ALL_JOURNALS, all available journals are loaded. If an
            integer value greater than 1 is provided, upto that many are loaded -
            most recent first.
        """
        # Use the journal_load to determine how many journal files we're
        # supposed to read.
        match self.journal_load:
            case JournalLoad.ALL_JOURNALS:
                max_journals = -1

            case JournalLoad.DO_NOT_LOAD | int() as n if n <= 0:
                self.journals_loaded.clear()
                self.journal.clear()
                self.events.clear()
                self.tdenv.DEBUG1("JournalLoad.DO_NOT_LOAD; cleared journals")
                return

            case JournalLoad.MOST_RECENT | int() as n if n == 1:
                max_journals = 1

            case int() as n:
                max_journals = n

            case _:
                raise GameException(f"Invalid journal load value: {self.journal_load}")
        
        # Sanity check: zero means zero, ie don't load anything.
        if max_journals == 0:
            raise RuntimeError("Internal error: zero max_journals escaped match")
        
        # Fetch the full list of files
        files = self.list_journals()
        if not files:
            raise JournalException(f"no journal logs found in {self.path}")

        # Positive count denotes an upper cound
        if max_journals > 0:
            files = files[:max_journals]
        
        # Now we need them in the reverse order so that newer values overwrite older.
        files.reverse()
        
        self.tdenv.DEBUG1("loading {} journal files: {}", len(files), files)
        with bench(self.tdenv, "_load_journal_files"):
            try:
                self._load_journal_files(files)
            except FileNotFoundError as e:
                raise JournalException(str(e)) from None

        if not self.journals_loaded:
            raise JournalException(f"no valid journal logs found in {self.path}")
    
    def _add_event(self, event: dict[str, Any] | None) -> None:
        """ @internal helper for registering an event into our fields """
        event_name = (event or {}).get("event", None)
        if not event_name:
            self.tdenv.DEBUG2("ignoring non-event: {}", event)
            return
        
        self.journal.append(event)
        try:
            self.history[event_name].append(event)
        except KeyError:
            self.history[event_name] = [event]
        self.events[event_name] = event
    
    def _load_journal_files(self, files: list[Path], *, loader: Any = orjson.loads) -> None:
        """
            @internal _load_journal_files loads events from the provided list of
            journal files into self.journals_loaded, self.journal, self.history,
            and self.events.
            @note silo'd for testability.
        """
        for journal_file in files:
            self.tdenv.DEBUG1("loading journal file: {}", journal_file)
            with journal_file.open("r", encoding="utf-8") as line_stream:
                lines = iter(line_stream)
                try:
                    header = loader(next(lines))
                except (StopIteration, orjson.JSONDecodeError):
                    raise JournalException("Unable to read journals: Please wait for Elite Dangerous to finish loading") from None
                
                try:
                    # Use an iterator so we can siphon off the first line as a header
                    if not self._read_journal_header(journal_file, header):
                        continue
                    self.tdenv.DEBUG0(
                        "{}: elite {} build {} lang {} odyssey {}",
                        journal_file,
                        header.get("gameversion", "unknown"),
                        header.get("build", "unknown"),
                        header.get("language", "unknown"),
                        header.get("Odyssey", "unknown")
                    )
                    
                    for line in lines:
                        data = loader(line)
                        self._add_event(data)
                    
                    self.journals_loaded.append(journal_file)
                
                except orjson.JSONDecodeError as e:
                    self.tdenv.WARN("failed to parse journal file {}: {}", journal_file, e)
    
    def _read_journal_header(self, journal_file: Path, header: dict) -> bool:
        """
            @internal _read_journal_header reads and validates the header line
            of a journal file. Returns True if successful, False to skip the file.
            @note silo'd for testability.
        """
        if not isinstance(header, dict) or header.get("event", "") != "Fileheader":
            self.tdenv.DEBUG0("ignoring invalid journal file {}, first line is not Fileheader: {}", journal_file, header)
            return False
        
        event: str = header["event"]
        if event not in self.history:
            self.history[event] = []
        self._add_event(header)
        
        return True
    
    def _load_json_files(self) -> None:
        if not self.json_files:
            self.json_data.clear()
            self.jsons_loaded.clear()
            self.tdenv.DEBUG1("no json files to load; cleared json data")
            return
        
        for json_file_enum in set(self.json_files):
            json_file_path = self.path / json_file_enum.value
            self.tdenv.DEBUG1("loading json file: {}", json_file_path)

            try:
                with json_file_path.open("r", encoding="utf-8") as json_stream:
                    data = orjson.loads(json_stream.read())
                    self.json_data[json_file_enum] = data
                    self.jsons_loaded += [json_file_enum]
                    self._add_event(data)
            except FileNotFoundError as e:
                raise MissingJsonError(str(e)) from None
            except orjson.JSONDecodeError as e:
                raise JsonException(f"unable to parse save-game json file {json_file_path}: {e}") from None
    
    def get_status(self) -> Status:
        """
            get_status creates or returns a cached summary of the
            already-loaded json status.
        """
        if self.status:
            return self.status
        
        # Start a new one
        status = Status()

        # Collect journal events.
        for event in self.journal:
            match event.get("event"):
                case "Location" | "FSJump" | "CarrierJump":
                    status.star_system = event.get("StarSystem") or status.star_system  # incase it's empty
                    status.system_address = event.get("SystemAddress", status.system_address)
                    status.docked = event.get("Docked", status.docked)
                    status.landed = event.get("Landed", status.landed)
                    if status.docked:
                        status.station_name = event.get("StationName", status.station_name)
                        status.station_type = event.get("StationType", status.station_type)

                case "Cargo":
                    if event.get("Vessel") == "Ship":
                        status.cargo_load = event.get("Count")
                
                case "Docked":
                    status.docked = True
                    status.landed = False
                    status.station_name = event.get("StationName", status.station_name)
                    status.station_type = event.get("StationType", status.station_type)
                    status.star_system = event.get("StarSystem", status.star_system)
                    status.system_address = event.get("SystemAddress", status.system_address)

                case "Loadout":
                    status.cargo_space = event.get("CargoCapacity")
                
                case "Undocked":
                    status.docked = False
                    status.station_name = None
                    status.station_type = None
                
                case "Touchdown" | "Landed":
                    status.docked = False
                    status.landed = True
                
                case "Liftoff":
                    status.docked = status.landed = False
                
                case "Commander":
                    status.commander = event.get("Name")
                    status.fid = event.get("FID")
                
                case "LoadGame":
                    status.commander = event.get("Commander")
                    status.fid = event.get("FID")
                
                case "Status":
                    status.credits = event.get("Balance")
                    status.destination = event.get("Destination")
                
                case _:
                    continue  # TERMINATE
            
            if not status.docked and not status.landed:
                status.station_name = status.station_type = None
            
            status.timestamp = event.get("timestamp", status.timestamp)
        
        self.status = status
        
        return status


def journal_path(tdenv: TradeEnv, path: str | Path | None) -> Path:
    """ Attempts to locate the elite savegame folder. """
    candidate: Path | str | None = None
    source: str | None = None
    
    if path:
        # the caller is providing an explicit path, they win.
        source, candidate = "path", path
    elif (env_path := getattr(tdenv, "journal_path", None)):
        # configured on the context object, it wins
        source, candidate = "tdenv.journal_path", env_path
    elif (env_path := os.getenv(ELITE_JOURNAL_ENVVAR, None)):
        # environment variable fallback
        source, candidate = ELITE_JOURNAL_ENVVAR, env_path
    elif WINDOWS_JOURNAL_DIR.exists():
        source, candidate = "windows", WINDOWS_JOURNAL_DIR
    elif MACOS_JOURNAL_DIR.exists():
        source, candidate = "macos", MACOS_JOURNAL_DIR
    
    if not candidate:
        raise GameFolderError("Could not determine the default path for this machine")
    
    tdenv.DEBUG0("journal_path: {}: {}", source, path)
    
    path = Path(candidate)
    if not path.exists():
        raise GameFolderError(f"'{candidate}' does not exist")
    
    return path


def require_game_data(
    game: EliteGame,
    *,
    cargo: bool = False,        # Short for cargo_space + cargo_load
    cargo_space: bool = False,  # Size of cargo hold
    cargo_load: bool = False,   # Current units of cargo
    commander: bool = False,
    credits: bool = False,
    location: bool = False,
    navroute: bool = False,
    status_fields: Iterable[str] | None = None,  # list of fields you need status to have.
) -> None:
    """ Checks the game object has the data it needs to provide
        specific status fields, and if not raises an exception
        with user guidance. """
    # Fields that we'll want to check aren't "None"
    none_checks: set[str] = set()  # not to be confused with nun_chucks

    #### EVENTS

    # We require that one item from each subset is present,
    # that is: all(any(subset) for subset in events)
    events: set[str | Iterable[str]] = set()

    if cargo or cargo_space:
        events.add(("Loadout",))    # The ship's load out, i.e its capacity
        none_checks.add("cargo_space")
    if cargo or cargo_load:
        events.add(("Cargo",))      # The ship's cargo content, i.e cargo hold use
        none_checks.add("cargo_load")

    if commander:
        events.add(("Commander", "LoadGame"))  # either will do
        none_checks.add("commander")

    if credits:
        events.add(("Status",))
        none_checks.add("credits")

    if location:
        events.add((
            "CarrierJump",
            "Docked",
            "FSJump",
            "Location",
        ))

    missing = set()
    for subset in events:
        has_any = any(event in game.events for event in subset)
        if has_any:
            continue
        for event in subset:
            missing.add(event)

    #### JSON loads/events
    if navroute:
        if not game.json_data.get(JsonFiles.NAVROUTE, {}):
            missing.add("NavRoute data")

    #### None checks

    # Now we'll check that there are meaningful values on fields the caller wants to access.
    status: Status = game.get_status()

    check_attrs = none_checks | set(status_fields or ())
    for field in check_attrs:
        try:
            if getattr(status, field) is None:
                missing.add(f"'{field}' value")
        except AttributeError:
            raise RuntimeError(f"Internal Error: Checking for unrecognized game-data field '{field}'")

    if missing:
        missing_things = sorted(missing)
        raise GameDataException(
            "Your current game is missing information required to "
            f"serve this request: {', '.join(missing_things)}"
        )
