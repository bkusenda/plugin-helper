# Plugin Helper

## Description

A simple Python plugin manager that can be used to track,install, load and uninstall plugins at runtime.

## Features

- Plugins follow standard python packaging and can be located locally, in a git repository, or in PyPi
- Supports multiple repositories
- Installed into current virtual python environemnt automatically
- Uses JSON for repo and plugin tracking

## Requirements

- Currently requires 'activate' script from conda to target current virtual env (TODO: remove this requirement)

## Installation

```bash
pip install https://github.com/bkusenda/plugin-helper
```

## Usage

From within your project with module name: "myproj"

```python

from plugin_helper import PluginHelper

ph = PluginHelper(category = "plugin_category",proj_module_name = 'myproj')

print("Plugins available for install.")
print(ph.available_plugins())

plugin_id = "myproj-myplugin-name"

# Installation: Run once
ph.install_plugin(plugin_id)

# Load all Plugins: To be used at module load time (loads all plugins)
pg.load_plugins()

# Uninstall:  Run once
pm.uninstall_plugin(plugin_id)

```

## Example Plugin Definition

```json
[
    {
      "id": "example-plugin-1",
      "version": "1.0",
      "name": "Example Plugin 1",
      "description": "",
      "author": "Author Name"
    }
  ]
```

## Full Plugin Example

see: [plugins/](plugins/)

## Development

Contributions are welcome!
