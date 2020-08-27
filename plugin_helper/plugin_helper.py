import os
import json
import importlib
import pkg_resources
import subprocess
import logging
import sys
from pathlib import Path
import urllib.request, json 


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


def get_default_config_dir(proj_module_name):
    home = str(Path.home())
    return os.path.join(home, ".{}".format(proj_module_name))


class PluginHelper:
    """
    Naming Requirements:
     - plugin package name = plugin_id
     - plugin module name = plugin_id with hyphans replaced with underscores
     - proj_module_name = module using pluginhelper
     - builtin plugin repo should be put in your main project package under "plugins/category/" directory
    """

    def __init__(self, category, proj_module_name):
        self.proj_module_name = proj_module_name
        self.category = category
        self.plugin_path = os.path.join(
            get_default_config_dir(proj_module_name), "plugins", self.category
        )
        os.makedirs(self.plugin_path, exist_ok=True)

        self.sources = None
        self.all_p = None
        self.installed_p = None

    def get_sources(self):
        if self.sources is not None:
            return self.sources

        self.sources = open_json_file(os.path.join(self.plugin_path, "sources.json"))

        if self.sources is None:
            self.sources = {}
            self.sources["builtin"] = {
                "id": "builtin",
                "type": "file",
                "name": "Built-in",
                "description": "",
                "path": self.get_builtin_plugin_path(),
            }
            self.sources["custom"] = {
                "id": "custom",
                "type": "file",
                "name": "Custom Local Plugin",
                "description": "",
                "path": os.path.join(self.plugin_path, "custom_repo"),
            }
            save_to_json_file(
                self.sources, os.path.join(self.plugin_path, "sources.json")
            )
        return self.sources

    def plugin_id_to_module_name(self, plugin_id):
        return plugin_id.replace("-", "_")

    def get_all_plugins(self):
        if self.all_p is not None:
            return self.all_p

        self.all_p = {}
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
                    self.all_p[plugin_desc["id"]] = plugin_desc
        return self.all_p

    def get_installed_plugins(self):
        if self.installed_p is not None:
            return self.installed_p
        self.installed_p = open_json_file(
            os.path.join(self.plugin_path, "installed.json")
        )
        if self.installed_p is None:
            self.installed_p = {}
        return self.installed_p

    def get_available_plugins(self):

        all_plugins = self.get_all_plugins()
        installed_plugins = self.get_installed_plugins()

        available_p = {}
        for key in all_plugins.keys():
            if key not in installed_plugins:
                available_p[key] = all_plugins[key]
        return available_p

    def get_builtin_plugin_path(self):
        module = importlib.import_module(self.proj_module_name)
        builtin_root_path = os.path.abspath(
            os.path.join(os.path.dirname(module.__file__), "..", "plugins")
        )
        return os.path.join(builtin_root_path, self.category)

    def _run_entrypoint(self, entrypoint_name, plugin_id=None):
        module_name = None
        if plugin_id is not None:
            module_name = self.plugin_id_to_module_name(plugin_id)

        results = {}
        for ep in pkg_resources.iter_entry_points(
            group="{}_plugin".format(self.proj_module_name), name=entrypoint_name
        ):
            if module_name is None or ep.module_name == "{}.main".format(module_name):
                results[ep.module_name] = ep.load()()
        return results

    def _run_bash_command(self, cmd):
        logging.debug("BASH COMMAND \n\t{}".format(cmd))
        return subprocess.check_output(
            '/bin/bash -c "{}"'.format(cmd), shell=True, text=True
        )

    def _run_plugin_package_install(self, plugin):
        virtenv = get_virtenv()
        cmd = None
        if plugin["source"]["type"] == "file":
            full_path = os.path.join(self.get_builtin_plugin_path(), plugin["id"])
            cmd = "source activate {} ; cd {} ; pip install --editable .".format(
                virtenv, full_path
            )
        elif plugin["source"]["type"] == "url":
            url = plugin.get("path")
            if url is None:
                url = os.path.join(plugin["source"]["path"], plugin["id"])
            cmd = "source activate {} ; cd {} ; pip install {}".format(virtenv, url)
        else:
            cmd = "source activate {} ; cd {} ; pip install {}".format(
                virtenv, plugin["id"]
            )
        return self._run_bash_command(cmd)

    def _run_plugin_package_remove(self, plugin):
        import importlib

        virtenv = get_virtenv()
        cmd = "source activate {} ; pip uninstall -y {}".format(virtenv, plugin["id"])
        return self._run_bash_command(cmd)

    def load_plugins(self):
        return self._run_entrypoint("load")

    def install_plugin(self, key):
        plugin = self.get_available_plugins().get(key)
        if plugin is None:
            raise Exception("Plugin {} not available or already installed.".format(key))
        logging.debug("Installing {}".format(key))
        result = self._run_plugin_package_install(plugin)
        logging.debug("Package Install Output\n {}".format(result))

        entrypoint_result = self._run_entrypoint("install", plugin_id=key)
        logging.debug("Plugin Install Output\n {}".format(entrypoint_result))

        self.installed_p = self.get_installed_plugins()
        self.installed_p[key] = plugin
        save_to_json_file(
            self.installed_p, os.path.join(self.plugin_path, "installed.json")
        )
        return True

    def reload_plugin_by_id(self, key):
        module_name = self.plugin_id_to_module_name(key)
        module = importlib.import_module(module_name)
        importlib.reload(module)

    def uninstall_plugin(self, key):
        logging.debug("Uninstalling {}".format(key))
        plugin = self.get_installed_plugins().get(key)
        entrypoint_result = self._run_entrypoint("uninstall", plugin_id=key)
        logging.debug("Plugin Uninstall Output\n {}".format(entrypoint_result))
        remove_result = self._run_plugin_package_remove(plugin)
        logging.debug("Package Uninstall Output\n {}".format(remove_result))

        self.installed_p = self.get_installed_plugins()
        self.installed_p.pop(key)
        save_to_json_file(
            self.installed_p, os.path.join(self.plugin_path, "installed.json")
        )
        return True
