import pytest

class TestBootstrapPlugins:
    def test_import_traded(self):
        import tradedangerous as td
    
    def test_import_plugins(self):
        from tradedangerous import plugins
    
    def test_import_plugins_eddblink(self):
        from tradedangerous.plugins import eddblink_plug
    
    @pytest.mark.skip("edapi requires secrets and stuff")
    def test_import_plugins_edapi(self):
        from tradedangerous.plugins import edapi_plug
    
    def test_import_plugins_edcd(self):
        from tradedangerous.plugins import edcd_plug
    
    def test_import_plugins_edmc_batch(self):
        from tradedangerous.plugins import edmc_batch_plug
    
    def test_import_plugins_journal(self):
        from tradedangerous.plugins import journal_plug
    
    def test_import_plugins_netlog(self):
        from tradedangerous.plugins import netlog_plug
