import unittest


class TestBootstrapCommands(unittest.TestCase):
    def test_import_commands(self):
        from tradedangerous import commands
        
        self.assertIn('buildcache', commands.commandIndex)
        self.assertIn('buy', commands.commandIndex)
    
    def test_import_buildcache_cmd(self):
        from tradedangerous.commands import buildcache_cmd
    
    def test_import_buy(self):
        from tradedangerous.commands import buy_cmd
    
    def test_import_import_cmd(self):
        from tradedangerous.commands import import_cmd
    
    def test_import_local_cmd(self):
        from tradedangerous.commands import local_cmd
    
    def test_import_market_cmd(self):
        from tradedangerous.commands import market_cmd
    
    def test_import_nav_cmd(self):
        from tradedangerous.commands import nav_cmd
    
    def test_import_olddata_cmd(self):
        from tradedangerous.commands import olddata_cmd
    
    def test_import_rares_cmd(self):
        from tradedangerous.commands import rares_cmd
    
    def test_import_run_cmd(self):
        from tradedangerous.commands import run_cmd
    
    def test_import_sell_cmd(self):
        from tradedangerous.commands import sell_cmd
    
    def test_import_shipvendor_cmd(self):
        from tradedangerous.commands import shipvendor_cmd
    
    def test_import_station_cmd(self):
        from tradedangerous.commands import station_cmd
    
    def test_import_update_cmd(self):
        from tradedangerous.commands import update_cmd
    
    def test_import_update_gui(self):
        from tradedangerous.commands import update_gui
