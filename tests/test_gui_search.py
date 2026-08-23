import pytest
from sqlalchemy.exc import OperationalError

from tradedangerous.db.orm_models import System
from tradedangerous.guiapp.gui_search import (
    GuiSearchDatabaseError,
    GuiSearchService,
)


def _make_search_service(tmp_path, request, database_name):
    config_path = tmp_path / f'{database_name}.ini'
    config_path.write_text(
        '[database]\n'
        'backend = sqlite\n'
        '\n'
        '[paths]\n'
        f'data_dir = {tmp_path}\n'
        f'tmp_dir = {tmp_path}\n'
        '\n'
        '[sqlite]\n'
        f'sqlite_filename = {database_name}.db\n',
        encoding='utf-8',
    )
    service = GuiSearchService(cfg_path=config_path)
    request.addfinalizer(service.engine.dispose)
    return service


def test_valid_database_preserves_no_result_semantics(tmp_path, request):
    service = _make_search_service(tmp_path, request, 'valid-empty')
    System.__table__.create(service.engine)
    assert service.resolve_system('Something Missing') is None
    assert service.suggest_systems('Something Missing') == []


@pytest.mark.parametrize(
    'method_name',
    [
        'suggest_systems',
        'resolve_system',
        'suggest_items',
        'suggest_buy_search',
        'suggest_run_avoid',
        'suggest_stations',
    ],
)
def test_public_database_searches_translate_query_failures(
    tmp_path,
    request,
    method_name,
):
    service = _make_search_service(tmp_path, request, method_name)
    with pytest.raises(GuiSearchDatabaseError) as raised:
        getattr(service, method_name)('Something Missing')
    assert isinstance(raised.value.__cause__, OperationalError)
    assert 'no such table' in str(raised.value.__cause__)
