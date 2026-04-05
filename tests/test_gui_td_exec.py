from types import SimpleNamespace

from tradedangerous.guiapp.td_exec import (
    GuiCommandRequest,
    TdExecutor,
    _snapshot_structured_result,
)

class _FakeSystem:
    def __init__(self, name):
        self.dbname = name
        self.posX = 1.0
        self.posY = 2.0
        self.posZ = 3.0
        self.stations = []
    
    def name(self):
        return self.dbname

class _FakeStation:
    def __init__(self, name, system):
        self.dbname = name
        self.system = system
        self.lsFromStar = 42
        self.market = 'Y'
        self.blackMarket = 'N'
        self.shipyard = 'Y'
        self.outfitting = 'N'
        self.rearm = 'Y'
        self.refuel = 'Y'
        self.repair = 'N'
        self.maxPadSize = 'L'
        self.planetary = 'N'
        self.fleet = 'N'
        self.odyssey = 'Y'
        self.itemCount = 3
    
    def name(self, *_args):
        return f'{self.system.dbname}/{self.dbname}'
    
    def distFromStar(self):
        return '42'

class _FakeTrade:
    def __init__(self, name, cost, gain):
        self._name = name
        self.costCr = cost
        self.gainCr = gain
    
    def name(self):
        return self._name

class _FakeHop:
    def __init__(self, items, units, gain, gpt):
        self.items = items
        self.units = units
        self.gainCr = gain
        self.gpt = gpt

class _FakeRoute:
    def __init__(self, route, hops, jumps):
        self.route = route
        self.hops = hops
        self.jumps = jumps
        self.firstStation = route[0]
        self.lastStation = route[-1]
        self.startCr = 1000
        self.gainCr = 450
        self.gpt = 45
        self.score = 12.5

def test_td_exec_request_context_precedence():
    request = GuiCommandRequest(
        command='run',
        global_values={'credits': 1000, 'capacity': 10},
        ship_profile_values={'capacity': 20, 'jump_range_full_ly': 15},
        context_overrides={'capacity': 30, 'starting': 'Sol'},
        main_values={'starting': 'Achenar', 'hops': 4},
        advanced_values={'hops': 6, 'routes': 2},
    )
    
    assert request.effective_context() == {
        'credits': 1000,
        'capacity': 30,
        'jump_range_full_ly': 15,
        'starting': 'Sol',
    }
    assert request.resolved_values() == {
        'credits': 1000,
        'capacity': 30,
        'jump_range_full_ly': 15,
        'starting': 'Achenar',
        'hops': 6,
        'routes': 2,
    }

def test_td_executor_validate_request_core_rules_per_command():
    executor = TdExecutor()
    
    run_errors = executor.validate_request(GuiCommandRequest(command='run'))
    trade_errors = executor.validate_request(GuiCommandRequest(command='trade'))
    local_errors = executor.validate_request(GuiCommandRequest(command='local'))
    market_errors = executor.validate_request(GuiCommandRequest(command='market'))
    nav_errors = executor.validate_request(GuiCommandRequest(command='nav'))
    olddata_errors = executor.validate_request(
        GuiCommandRequest(command='olddata', main_values={'route': True})
    )
    
    assert 'Run requires Capacity.' in run_errors
    assert 'Run requires Credits.' in run_errors
    assert 'Run requires Jump Range (Full).' in run_errors
    assert trade_errors == ['Trade requires Origin.', 'Trade requires Destination.']
    assert local_errors == ['Local requires Near.']
    assert market_errors == ['Market requires Station.']
    assert nav_errors == ['Nav requires Start.', 'Nav requires End.']
    assert olddata_errors == ['Old Data route sorting requires Near.']

def test_td_exec_snapshot_helpers_convert_live_objects_to_plain_data():
    origin_system = _FakeSystem('Sol')
    dest_system = _FakeSystem('LHS 380')
    origin = _FakeStation('Abraham Lincoln', origin_system)
    destination = _FakeStation('Fisher Point', dest_system)
    trade = _FakeTrade('Hydrogen Fuel', 50, 25)
    hop = _FakeHop(items=[(trade, 10)], units=10, gain=250, gpt=25)
    route = _FakeRoute(
        route=[origin, destination],
        hops=[hop],
        jumps=[[origin_system, dest_system]],
    )
    
    snapshot = _snapshot_structured_result('run', [route])
    
    assert snapshot == [{
        'first_station': 'Sol/Abraham Lincoln',
        'last_station': 'LHS 380/Fisher Point',
        'startCr': 1000,
        'gainCr': 450,
        'gpt': 45,
        'score': 12.5,
        'hops': [{
            'src_station': 'Sol/Abraham Lincoln',
            'dst_station': 'LHS 380/Fisher Point',
            'units': 10,
            'gainCr': 250,
            'gpt': 25,
            'items': [{
                'commodity': 'Hydrogen Fuel',
                'qty': 10,
                'buy': 50,
                'sell': 75,
                'gain': 25,
                'total': 250,
            }],
            'jump_path': ['Sol', 'LHS 380'],
        }],
    }]
