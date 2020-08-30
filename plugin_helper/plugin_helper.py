import os
import json
import importlib
import pkg_resources
import subprocess
import logging
import sys
from pathlib import Path
import urllib.request, json 
import time
from filelock import FileLock
import uuid
def open_json_file(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError as e:
        return None


def save_to_json_file(data, path):
    with open(path, "w") as f:
        json.dump(data, f)


def get_virtenv():
    return Path(sys.executable).as_posix().split("/")[-3]


def get_home():
    return str(Path.home())

def get_activate_path():
    return os.path.join(get_home(),"anaconda3/bin/activate")

def get_default_config_dir(proj_module_name):
    home = str(Path.home())
    return os.path.join(home, ".{}".format(proj_module_name))


class PluginHelper:
    """
    Naming Requirements:
     - plugin package name = plugin_id
     - plugin module name = plugin_id with hyphans replaced with underscores
     - proj_module_name = module using pluginhelper
     - builtin plugin repo should be put in your main project package under "plugins/" directory
    """

    def __init__(self, proj_module_name, plugin_path=None, instance_id = None):

               
        self.proj_module_name = proj_module_name
        if instance_id is None:
            instance_id = str(uuid.uuid1())

        self.instance_id = instance_id
        if plugin_path is None:
            self.plugin_path = os.path.join(get_default_config_dir(proj_module_name), "plugins")
        else:
            self.plugin_path = plugin_path

        os.makedirs(self.plugin_path, exist_ok=True)

        timestr = time.strftime("%Y%m%d-%H%M%S")

        log_root = os.path.join(self.plugin_path, "logs")
        os.makedirs(log_root, exist_ok=True)


        # Setup Logging
        log_filename = os.path.join(log_root, "{}.log".format(timestr))
        logging.info("FILE LOGGING TO {}".format(log_filename))

        logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
        self.logger = logging.getLogger()

        fileHandler = logging.FileHandler(log_filename)
        fileHandler.setFormatter(logFormatter)
        self.logger.addHandler(fileHandler)

        consoleHandler = logging.StreamHandler()
        consoleHandler.setFormatter(logFormatter)
        self.logger.addHandler(consoleHandler)
        self.logger.setLevel(logging.DEBUG)

        # Clean up
        self.clear_old_transit_states()       
        

    def get_sources(self):

        sources = open_json_file(os.path.join(self.plugin_path, "sources.json"))

        if sources is None:
            sources = {}
            sources["builtin"] = {
                "id": "builtin",
                "type": "file",
                "name": "Built-in",
                "description": "",
                "path": self.get_builtin_plugin_path(),
            }
            sources["custom"] = {
                "id": "custom",
                "type": "file",
                "name": "Custom Local Plugin",
                "description": "",
                "path": os.path.join(self.plugin_path, "custom_repo"),
            }
            save_to_json_file(
                sources, os.path.join(self.plugin_path, "sources.json")
            )
        return sources

    def plugin_id_to_module_name(self, plugin_id):
        return plugin_id.replace("-", "_")

    def get_plugins_from_sources(self):
        all_p = {}
        for source in self.get_sources().values():
            plugins = None
            if source["type"] == "url":
                with urllib.request.urlopen(source["path"]) as url:
                    plugins = json.loads(url.read().decode())
            elif source["type"] == "file":
                plugins = open_json_file(os.path.join(source["path"], "repo.json"))

            if plugins is not None:
                for plugin_desc in plugins:
                    plugin_desc["source"] = source
                    all_p[plugin_desc["id"]] = plugin_desc
        for plugin in all_p.values():
            plugin['status'] = {'state':"AVAIL"}
        return all_p

    def get_installed_plugins(self):
        installed_p = open_json_file(
            os.path.join(self.plugin_path, "installed.json")
        )
        if installed_p is None:
            installed_p = {}

        return installed_p

    def get_all_plugins(self):
        plugins = self.get_plugins_from_sources()
        installed_p = self.get_installed_plugins()
        plugins.update(installed_p)
        return plugins

    def get_builtin_plugin_path(self):
        module = importlib.import_module(self.proj_module_name)
        builtin_root_path = os.path.abspath(
            os.path.join(os.path.dirname(module.__file__), "..", "plugins")
        )
        return os.path.join(builtin_root_path)

    def _run_entrypoint(self, entrypoint_name, plugin_id=None, entrypoint_kwargs={}):
        module_name = None
        if plugin_id is not None:
            module_name = self.plugin_id_to_module_name(plugin_id)

        results = {}
        for ep in pkg_resources.iter_entry_points(
            group="{}_plugin".format(self.proj_module_name), name=entrypoint_name
        ):
            if module_name is None or ep.module_name == "{}.plugin".format(module_name):
                entrypoint_func = ep.load()
                results[ep.module_name] = entrypoint_func(**entrypoint_kwargs)
        return results

    def _run_bash_command(self, cmd):
        self.logger.debug("BASH COMMAND \n\t{}".format(cmd))
        return subprocess.check_output(
            '/bin/bash -c "{}"'.format(cmd), shell=True, text=True
        )

    def _run_plugin_package_install(self, plugin):
        virtenv = get_virtenv()
        print("Using Virt {}".format(virtenv))
        cmd = None
        if plugin["source"]["type"] == "file":
            full_path = os.path.join(self.get_builtin_plugin_path(), plugin["id"])
            cmd = "source {} {} ; cd {} ; pip install --editable .".format(get_activate_path(),
                virtenv, full_path
            )
        elif plugin["source"]["type"] == "url":
            url = plugin.get("path")
            if url is None:
                url = os.path.join(plugin["source"]["path"], plugin["id"])
            cmd = "source {} {} ; cd {} ; pip install {}".format(get_activate_path(),virtenv, url)
        else:
            cmd = "source {} {} ; cd {} ; pip install {}".format(get_activate_path(),
                virtenv, plugin["id"]
            )
        return self._run_bash_command(cmd)

    def _run_plugin_package_remove(self, plugin):
        virtenv = get_virtenv()
        cmd = "source {} {} ; pip uninstall -y {}".format(get_activate_path(),virtenv, plugin["id"])
        return self._run_bash_command(cmd)

    def load_plugins(self):
        #TODO: Should I also provide the potentially faster option which just scans packages?
        lock = FileLock(os.path.join(self.plugin_path,".loading.lock"))
        with lock:
            for plugin in self.get_installed_plugins().values():
                return self._run_entrypoint("load",plugin['id'],entrypoint_kwargs=plugin.get("load_kwargs",{}))

    def update_plugin_status(self,plugin,state,msg=""):
        lock = FileLock(os.path.join(self.plugin_path,".updating.lock"))
        with lock:
            installed_p = self.get_installed_plugins()
            installed_p[plugin['id']] = plugin

            plugin['status'] = {'state':state, 'timestamp':time.time(),'msg':msg, 'instance_id':self.instance_id}
            save_to_json_file(
                installed_p, os.path.join(self.plugin_path, "installed.json")
            )

    def clear_old_transit_states(self):
        for plugin in self.get_installed_plugins().values():
            if plugin['status']['state'] in ["INSTALLING","UNINSTALLING"] and plugin['status']['instance_id'] != self.instance_id:
                self.update_plugin_status("INSTALLED")
                    

    def get_plugin_state(self,plugin_id):
        plugin = self.get_all_plugins().get(plugin_id)
        if plugin is None:
            return None
        else:
            return plugin['status']['state']
        
    def remove_plugin_by_id(self,plugin_id):
        lock = FileLock(os.path.join(self.plugin_path,".updating.lock"))
        with lock:
            installed_p = self.get_installed_plugins()
            installed_p.pop(plugin_id)
            save_to_json_file(
                installed_p, os.path.join(self.plugin_path, "installed.json")
            )

    def install_plugin(self, plugin_id):

        plugin = self.get_all_plugins().get(plugin_id)
        if plugin is None:
            raise Exception("Plugin {} not found.".format(plugin_id))
        elif plugin['status']['state'] in ["INSTALLING","UNINSTALLING"]:
            raise Exception("Cannot perform action. Plugin {} is currently {}.".format(plugin_id,plugin['status']['state']))

        self.update_plugin_status(plugin,"INSTALLING")

        try:
        
            # Run Installion
            self.logger.debug("Installing {}".format(plugin_id))
            result = self._run_plugin_package_install(plugin)
            self.logger.debug("Package Install Output\n {}".format(result))
            importlib.import_module(self.plugin_id_to_module_name(plugin_id))


            entrypoint_result = self._run_entrypoint("install", plugin_id=plugin_id)
            self.logger.debug("Plugin Install Output\n {}".format(entrypoint_result))
            
            # Mark as INSTALLED
            self.update_plugin_status(plugin,"INSTALLED")
            return True
        except Exception as e:
            self.logger.error(e)
            self.update_plugin_status(plugin,"INSTALL_FAILED",msg="{}".format(e))
            return False

    def reload_plugin_by_id(self, plugin_id):
        module_name = self.plugin_id_to_module_name(plugin_id)
        module = importlib.import_module(module_name)
        importlib.reload(module)

    def uninstall_plugin(self, plugin_id):
        self.logger.debug("Uninstalling {}".format(plugin_id))
        installed_p = self.get_installed_plugins()
        plugin = installed_p.get(plugin_id)
        if plugin['status']['state'] in ["INSTALLING","UNINSTALLING"]:
            raise Exception("Cannot perform action. Plugin {} is currently {}.".format(plugin_id,plugin['status']['state']))

        # Mark as INSTALLING
        self.update_plugin_status(plugin,"UNINSTALLING")

        try:
            # Run Uninstallion
            entrypoint_result = self._run_entrypoint("uninstall", plugin_id=plugin_id)
            self.logger.debug("Plugin Uninstall Output\n {}".format(entrypoint_result))
            remove_result = self._run_plugin_package_remove(plugin)
            self.logger.debug("Package Uninstall Output\n {}".format(remove_result))
    
            # Remove Plugin Entry
            self.remove_plugin_by_id(plugin_id)
            return True

        except Exception as e:
            self.logger.error(e)
            self.update_plugin_status(plugin,"UNINSTALL_FAILED",msg="{}".format(e))
            return False
        
