import unittest
from plugin_helper.plugin_helper import PluginHelper
from plugin_helper.plugin_helper import get_default_config_dir
from pathlib import Path
import os

class TestMain(unittest.TestCase):

    def setUp(self):

        config_dir = get_default_config_dir('plugin_helper')
        installed_path = os.path.join(config_dir,'plugins','installed.json')
        if os.path.exists(installed_path):
            with open(installed_path) as f:
                Path.unlink(f,missing_ok = True)




    def test_install(self):
        ph = PluginHelper(category = "category",proj_module_name = 'plugin_helper')
        print(ph.get_installed_plugins())
        print(ph.get_available_plugins())
        plugin_id ='example-plugin-1'
        assert(len(ph.get_available_plugins()) == 1)
        ph.install_plugin(plugin_id)
        ph.load_plugins()
        ph.uninstall_plugin(plugin_id)
        assert(True)
        
       