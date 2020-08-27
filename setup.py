from setuptools import setup, find_packages

setup(
    name="plugin-helper",
    version="0.0.1",
    author="Brandyn Kusenda",
    author_email="pistar3.14@gmail.com",
    description="Simple Plugin Manager",
    long_description='',
    url="https://github.com/bkusenda/plugin-helper",
    license='',
    install_requires=[],
    package_data={'plugin-helper': ['README.md','tests/*','plugins/*']
      },
    packages=find_packages(),
    entry_points={},
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7'
    ],
    python_requires='>=3.6',
)