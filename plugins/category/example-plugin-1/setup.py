from setuptools import setup, find_packages

setup(
    name="example-plugin-1",
    version="0.0.1",
    author="Author Name",
    author_email="email",
    description="description",
    long_description='Long description',
    url="https://github.com/bkusenda/plugin-helper/plugins/category/example-plugin-1",
    license='',
    install_requires=[],
    package_data={'example-plugin-1': ['README.md']
      },
    packages=find_packages(),
    entry_points={
    'plugin_helper_plugin' : [
      "install =  example_plugin_1.main:install",
      "load =  example_plugin_1.main:load",
      "uninstall =  example_plugin_1.main:uninstall"]
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    python_requires='>=3.6',
)