from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sqlalchemy import func

from tradedangerous.db import get_session_factory, make_engine_from_config
from tradedangerous.db.orm_models import Category, Item, Ship, Station, System
from tradedangerous.db.paths import resolve_db_config_path

@dataclass(frozen=True, slots=True)
class Suggestion:
    """Tiny autocomplete payload for GUI text fields."""
    
    key: str
    kind: Literal['system', 'station', 'category', 'item', 'ship']
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
    
    def suggest_items(
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
            seen_item_ids: set[int] = set()
            base_query = (
                session.query(
                    Item.item_id,
                    Item.name.label('item_name'),
                    Category.name.label('category_name'),
                )
                .join(Category, Item.category_id == Category.category_id)
            )
            
            exact_rows = (
                base_query
                .filter(Item.name == query_text)
                .order_by(
                    Item.name,
                    Category.name,
                    Item.item_id,
                )
                .limit(bounded_limit)
                .all()
            )
            self._append_item_rows(
                suggestions=suggestions,
                seen_item_ids=seen_item_ids,
                rows=exact_rows,
            )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_query = base_query.filter(Item.name.like(f'{query_text}%'))
                if seen_item_ids:
                    prefix_query = prefix_query.filter(
                        ~Item.item_id.in_(seen_item_ids)
                    )
                prefix_rows = (
                    prefix_query
                    .order_by(
                        func.length(Item.name),
                        Item.name,
                        Category.name,
                        Item.item_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_item_rows(
                    suggestions=suggestions,
                    seen_item_ids=seen_item_ids,
                    rows=prefix_rows,
                )
            
            return suggestions
    
    def suggest_buy_search(
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
            seen_category_ids: set[int] = set()
            seen_item_ids: set[int] = set()
            seen_ship_ids: set[int] = set()
            
            exact_category_rows = (
                session.query(
                    Category.category_id,
                    Category.name.label('category_name'),
                )
                .filter(Category.name == query_text)
                .order_by(
                    Category.name,
                    Category.category_id,
                )
                .limit(bounded_limit)
                .all()
            )
            self._append_buy_category_rows(
                suggestions=suggestions,
                seen_category_ids=seen_category_ids,
                rows=exact_category_rows,
            )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                exact_item_rows = (
                    session.query(
                        Item.item_id,
                        Item.name.label('item_name'),
                        Category.name.label('category_name'),
                    )
                    .join(Category, Item.category_id == Category.category_id)
                    .filter(Item.name == query_text)
                    .order_by(
                        Item.name,
                        Category.name,
                        Item.item_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_buy_item_rows(
                    suggestions=suggestions,
                    seen_item_ids=seen_item_ids,
                    rows=exact_item_rows,
                )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                exact_ship_rows = (
                    session.query(
                        Ship.ship_id,
                        Ship.name.label('ship_name'),
                    )
                    .filter(Ship.name == query_text)
                    .order_by(
                        Ship.name,
                        Ship.ship_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_buy_ship_rows(
                    suggestions=suggestions,
                    seen_ship_ids=seen_ship_ids,
                    rows=exact_ship_rows,
                )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_category_query = (
                    session.query(
                        Category.category_id,
                        Category.name.label('category_name'),
                    )
                    .filter(Category.name.like(f'{query_text}%'))
                )
                if seen_category_ids:
                    prefix_category_query = prefix_category_query.filter(
                        ~Category.category_id.in_(seen_category_ids)
                    )
                prefix_category_rows = (
                    prefix_category_query
                    .order_by(
                        func.length(Category.name),
                        Category.name,
                        Category.category_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_buy_category_rows(
                    suggestions=suggestions,
                    seen_category_ids=seen_category_ids,
                    rows=prefix_category_rows,
                )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_item_query = (
                    session.query(
                        Item.item_id,
                        Item.name.label('item_name'),
                        Category.name.label('category_name'),
                    )
                    .join(Category, Item.category_id == Category.category_id)
                    .filter(Item.name.like(f'{query_text}%'))
                )
                if seen_item_ids:
                    prefix_item_query = prefix_item_query.filter(
                        ~Item.item_id.in_(seen_item_ids)
                    )
                prefix_item_rows = (
                    prefix_item_query
                    .order_by(
                        func.length(Item.name),
                        Item.name,
                        Category.name,
                        Item.item_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_buy_item_rows(
                    suggestions=suggestions,
                    seen_item_ids=seen_item_ids,
                    rows=prefix_item_rows,
                )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_ship_query = (
                    session.query(
                        Ship.ship_id,
                        Ship.name.label('ship_name'),
                    )
                    .filter(Ship.name.like(f'{query_text}%'))
                )
                if seen_ship_ids:
                    prefix_ship_query = prefix_ship_query.filter(
                        ~Ship.ship_id.in_(seen_ship_ids)
                    )
                prefix_ship_rows = (
                    prefix_ship_query
                    .order_by(
                        func.length(Ship.name),
                        Ship.name,
                        Ship.ship_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_buy_ship_rows(
                    suggestions=suggestions,
                    seen_ship_ids=seen_ship_ids,
                    rows=prefix_ship_rows,
                )
            
            return suggestions
            
    def suggest_run_avoid(
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
            seen_item_ids: set[int] = set()
            
            exact_system_rows = (
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
                rows=exact_system_rows,
            )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                exact_item_rows = (
                    session.query(
                        Item.item_id,
                        Item.name.label('item_name'),
                    )
                    .filter(Item.name == query_text)
                    .order_by(
                        Item.name,
                        Item.item_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_run_avoid_item_rows(
                    suggestions=suggestions,
                    seen_item_ids=seen_item_ids,
                    rows=exact_item_rows,
                )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_system_query = (
                    session.query(
                        System.system_id,
                        System.name,
                    )
                    .filter(System.name.like(f'{query_text}%'))
                )
                if seen_system_ids:
                    prefix_system_query = prefix_system_query.filter(
                        ~System.system_id.in_(seen_system_ids)
                    )
                prefix_system_rows = (
                    prefix_system_query
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
                    rows=prefix_system_rows,
                )
            
            remaining = bounded_limit - len(suggestions)
            if remaining > 0:
                prefix_item_query = (
                    session.query(
                        Item.item_id,
                        Item.name.label('item_name'),
                    )
                    .filter(Item.name.like(f'{query_text}%'))
                )
                if seen_item_ids:
                    prefix_item_query = prefix_item_query.filter(
                        ~Item.item_id.in_(seen_item_ids)
                    )
                prefix_item_rows = (
                    prefix_item_query
                    .order_by(
                        func.length(Item.name),
                        Item.name,
                        Item.item_id,
                    )
                    .limit(remaining)
                    .all()
                )
                self._append_run_avoid_item_rows(
                    suggestions=suggestions,
                    seen_item_ids=seen_item_ids,
                    rows=prefix_item_rows,
                )
            
            return suggestions
    
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
    def _append_buy_category_rows(
        *,
        suggestions: list[Suggestion],
        seen_category_ids: set[int],
        rows: list[object],
    ) -> None:
        for row in rows:
            category_id = int(row.category_id)
            if category_id in seen_category_ids:
                continue
            
            category_name = str(row.category_name)
            suggestions.append(
                Suggestion(
                    key=f'category:{category_id}',
                    kind='category',
                    value=category_name,
                    label=f'Category — {category_name}',
                    system_id=None,
                    system_name=None,
                    station_id=None,
                    station_name=None,
                )
            )
            seen_category_ids.add(category_id)
    
    @staticmethod
    def _append_buy_item_rows(
        *,
        suggestions: list[Suggestion],
        seen_item_ids: set[int],
        rows: list[object],
    ) -> None:
        for row in rows:
            item_id = int(row.item_id)
            if item_id in seen_item_ids:
                continue
            
            item_name = str(row.item_name)
            category_name = str(row.category_name)
            suggestions.append(
                Suggestion(
                    key=f'item:{item_id}',
                    kind='item',
                    value=item_name,
                    label=f'Item — {item_name} ({category_name})',
                    system_id=None,
                    system_name=None,
                    station_id=None,
                    station_name=None,
                )
            )
            seen_item_ids.add(item_id)
    
    @staticmethod
    def _append_buy_ship_rows(
        *,
        suggestions: list[Suggestion],
        seen_ship_ids: set[int],
        rows: list[object],
    ) -> None:
        for row in rows:
            ship_id = int(row.ship_id)
            if ship_id in seen_ship_ids:
                continue
            
            ship_name = str(row.ship_name)
            suggestions.append(
                Suggestion(
                    key=f'ship:{ship_id}',
                    kind='ship',
                    value=ship_name,
                    label=f'Ship — {ship_name}',
                    system_id=None,
                    system_name=None,
                    station_id=None,
                    station_name=None,
                )
            )
            seen_ship_ids.add(ship_id)
    
    @staticmethod
    def _append_run_avoid_item_rows(
        *,
        suggestions: list[Suggestion],
        seen_item_ids: set[int],
        rows: list[object],
    ) -> None:
        for row in rows:
            item_id = int(row.item_id)
            if item_id in seen_item_ids:
                continue
            
            item_name = str(row.item_name)
            suggestions.append(
                Suggestion(
                    key=f'item:{item_id}',
                    kind='item',
                    value=item_name,
                    label=f'Item — {item_name}',
                    system_id=None,
                    system_name=None,
                    station_id=None,
                    station_name=None,
                )
            )
            seen_item_ids.add(item_id)
    
    @staticmethod
    def _append_item_rows(
        *,
        suggestions: list[Suggestion],
        seen_item_ids: set[int],
        rows: list[object],
    ) -> None:
        for row in rows:
            item_id = int(row.item_id)
            if item_id in seen_item_ids:
                continue
            
            item_name = str(row.item_name)
            category_name = str(row.category_name)
            suggestions.append(
                Suggestion(
                    key=f'item:{item_id}',
                    kind='item',
                    value=item_name,
                    label=f'{item_name} — {category_name}',
                    system_id=None,
                    system_name=None,
                    station_id=None,
                    station_name=None,
                )
            )
            seen_item_ids.add(item_id)
    
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
