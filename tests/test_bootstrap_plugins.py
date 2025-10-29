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
    
    @pytest.mark.skip(reason="journal_plug plugin has been deprecated and archived")
    def test_import_plugins_journal(self):
        pytest.skip("journal_plug plugin is deprecated and archived")
    
    @pytest.mark.skip(reason="netlog_plug plugin has been deprecated and archived")
    def test_import_plugins_netlog(self):
        pytest.skip("netlog_plug plugin is deprecated and archived")
