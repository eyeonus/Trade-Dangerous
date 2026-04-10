from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import func

from tradedangerous.db import get_session_factory, make_engine_from_config
from tradedangerous.db.orm_models import Station, System
from tradedangerous.db.paths import resolve_db_config_path

@dataclass(frozen=True, slots=True)
class Suggestion:
    """Tiny autocomplete payload for GUI text fields."""
    
    key: str
    kind: Literal['system', 'station']
    value: str
    label: str
    system_id: int | None
    system_name: str | None
    station_id: int | None
    station_name: str | None

class GuiSearchService:
    """Lightweight DB-backed autocomplete provider for GUI drafts."""
    
    def __init__(
        self,
        *,
        cfg_path: str | Path | None = None,
    ) -> None:
        resolved_cfg = Path(cfg_path) if cfg_path is not None else resolve_db_config_path()
        self.engine = make_engine_from_config(str(resolved_cfg))
        self._session_factory = get_session_factory(self.engine)
    
    def suggest_systems(
        self,
        text: str,
        limit: int = 10,
    ) -> list[Suggestion]:
        query_text = self._clean_text(text)
        bounded_limit = self._clean_limit(limit)
        if not query_text or bounded_limit <= 0:
            return []
        
        with self._session_factory() as session:
            suggestions: list[Suggestion] = []
            seen_system_ids: set[int] = set()
            
            exact_rows = (
                session.query(
                    System.system_id,
                    System.name,
                )
                .filter(System.name == query_text)
                .order_by(
                    System.name,
                    System.system_id,
                )
                .limit(bounded_limit)
                .all()
            )
            self._append_system_rows(
                suggestions=suggestions,
                seen_system_ids=seen_system_ids,
                rows=exact_rows,
            )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_query = (
                    session.query(
                        System.system_id,
                        System.name,
                    )
                    .filter(System.name.like(f'{query_text}%'))
                )
                if seen_system_ids:
                    prefix_query = prefix_query.filter(
                        ~System.system_id.in_(seen_system_ids)
                    )
                prefix_rows = (
                    prefix_query
                    .order_by(
                        func.length(System.name),
                        System.name,
                        System.system_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_system_rows(
                    suggestions=suggestions,
                    seen_system_ids=seen_system_ids,
                    rows=prefix_rows,
                )
            
            return suggestions
    
    def resolve_system(self, text: str) -> Suggestion | None:
        query_text = self._clean_text(text)
        if not query_text:
            return None
        
        with self._session_factory() as session:
            row = (
                session.query(
                    System.system_id,
                    System.name,
                )
                .filter(System.name == query_text)
                .order_by(
                    System.name,
                    System.system_id,
                )
                .first()
            )
        
        if row is None:
            return None
        
        system_id = int(row.system_id)
        system_name = str(row.name)
        return Suggestion(
            key=f'system:{system_id}',
            kind='system',
            value=system_name,
            label=system_name,
            system_id=system_id,
            system_name=system_name,
            station_id=None,
            station_name=None,
        )
    
    def suggest_stations(
        self,
        text: str,
        limit: int = 10,
        system_id: int | None = None,
    ) -> list[Suggestion]:
        query_text = self._clean_text(text)
        bounded_limit = self._clean_limit(limit)
        if not query_text or bounded_limit <= 0:
            return []
        
        with self._session_factory() as session:
            suggestions: list[Suggestion] = []
            seen_station_ids: set[int] = set()
            base_query = (
                session.query(
                    Station.station_id,
                    Station.name.label('station_name'),
                    Station.system_id,
                    System.name.label('system_name'),
                )
                .join(System, Station.system_id == System.system_id)
            )
            
            if system_id is not None:
                base_query = base_query.filter(Station.system_id == int(system_id))
            
            exact_rows = (
                base_query
                .filter(Station.name == query_text)
                .order_by(
                    Station.name,
                    System.name,
                    Station.station_id,
                )
                .limit(bounded_limit)
                .all()
            )
            self._append_station_rows(
                suggestions=suggestions,
                seen_station_ids=seen_station_ids,
                rows=exact_rows,
            )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_query = base_query.filter(Station.name.like(f'{query_text}%'))
                if seen_station_ids:
                    prefix_query = prefix_query.filter(
                        ~Station.station_id.in_(seen_station_ids)
                    )
                prefix_rows = (
                    prefix_query
                    .order_by(
                        func.length(Station.name),
                        Station.name,
                        System.name,
                        Station.station_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_station_rows(
                    suggestions=suggestions,
                    seen_station_ids=seen_station_ids,
                    rows=prefix_rows,
                )
            
            return suggestions
    
    @staticmethod
    def _append_system_rows(
        *,
        suggestions: list[Suggestion],
        seen_system_ids: set[int],
        rows: list[object],
    ) -> None:
        for row in rows:
            system_id = int(row.system_id)
            if system_id in seen_system_ids:
                continue
            
            system_name = str(row.name)
            suggestions.append(
                Suggestion(
                    key=f'system:{system_id}',
                    kind='system',
                    value=system_name,
                    label=system_name,
                    system_id=system_id,
                    system_name=system_name,
                    station_id=None,
                    station_name=None,
                )
            )
            seen_system_ids.add(system_id)
    
    @staticmethod
    def _append_station_rows(
        *,
        suggestions: list[Suggestion],
        seen_station_ids: set[int],
        rows: list[object],
    ) -> None:
        for row in rows:
            station_id = int(row.station_id)
            if station_id in seen_station_ids:
                continue
            
            system_id = int(row.system_id)
            system_name = str(row.system_name)
            station_name = str(row.station_name)
            canonical_value = f'{system_name}/{station_name}'
            suggestions.append(
                Suggestion(
                    key=f'station:{station_id}',
                    kind='station',
                    value=canonical_value,
                    label=canonical_value,
                    system_id=system_id,
                    system_name=system_name,
                    station_id=station_id,
                    station_name=station_name,
                )
            )
            seen_station_ids.add(station_id)
    
    @staticmethod
    def _clean_limit(limit: int) -> int:
        try:
            numeric_limit = int(limit)
        except (TypeError, ValueError):
            return 0
        if numeric_limit < 0:
            return 0
        return min(numeric_limit, 50)
    
    @staticmethod
    def _clean_text(text: str) -> str:
        return str(text or '').strip()

_DEFAULT_SEARCH_SERVICE: GuiSearchService | None = None

def get_gui_search_service() -> GuiSearchService:
    """Return a process-local shared search service for GUI autocomplete."""
    
    global _DEFAULT_SEARCH_SERVICE
    
    if _DEFAULT_SEARCH_SERVICE is None:
        _DEFAULT_SEARCH_SERVICE = GuiSearchService()
    
    return _DEFAULT_SEARCH_SERVICE
