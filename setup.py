from setuptools import setup, find_packages
from cbpi import __version__
import platform

# read the contents of your README file
from os import popen, path
import os

localsystem = platform.system()
board_reqs = []
raspberrypi=False
if localsystem == "Linux":
    command="cat /proc/cpuinfo | grep 'Raspberry'"
    model=popen(command).read()
    if len(model) != 0:
        raspberrypi=True
        if os.path.exists("/proc/device-tree/compatible"):
          with open("/proc/device-tree/compatible", "rb") as f:
            compat = f.read()
            # Pi 5
            if b"brcm,bcm2712" in compat:
              board_reqs = [
              "rpi-lgpio"
              ]
            # Pi 4 and Earlier
            elif (
              b"brcm,bcm2835" in compat
              or b"brcm,bcm2836" in compat
              or b"brcm,bcm2837" in compat
              or b"brcm,bcm2838" in compat
              or b"brcm,bcm2711" in compat
              ):
              board_reqs = ["RPi.GPIO"]  

# read the contents of your README file
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='cbpi4',
      version=__version__,
      description='CraftBeerPi4 Brewing Software',
      author='Manuel Fritsch / Alexander Vollkopf',
      author_email='avollkopf@l@web.de',
      url='https://github.com/PiBrewing/craftbeerpi4',
      license='GPLv3',
      project_urls={
	    'Documentation': 'https://openbrewing.gitbook.io/craftbeerpi4_support/'},
      packages=find_packages(),
      include_package_data=True,
      package_data={
        # If any package contains *.txt or *.rst files, include them:
      '': ['*.txt', '*.rst', '*.yaml'],
      'cbpi': ['*','*.txt', '*.rst', '*.yaml']},

      python_requires='>=3.9',
      long_description=long_description,
	    long_description_content_type='text/markdown',
      install_requires=[
          "typing-extensions>=4",
          "aiohttp==3.13.3",
          "aiohttp-auth==0.1.1",
          "aiohttp-route-decorator==0.1.4",
          "aiohttp-security==0.5.0",
          "aiohttp-session==2.12.1",
          "aiohttp-swagger==1.0.16",
          "aiojobs==1.4.0 ",
          "aiosqlite==0.22.1",
          "cryptography==46.0.5",
          "pyopenssl==25.3.0",
          "requests==2.32.5",
          "voluptuous==0.15.2",
          "pyfiglet==1.0.4",
          'click==8.3.1',
          'shortuuid==1.0.13',
          'tabulate==0.9.0',
          'aiomqtt==2.5.0',
          'inquirer==3.4.1',
          'colorama==0.4.6',
          'psutil==7.1.3',
          'cbpi4gui',
          'importlib_metadata',
          'distro>=1.8.0',
          'numpy==2.3.5',
          'pandas==2.3.3'] + board_reqs + (
          ['systemd-python'] if localsystem == "Linux" else [] ),

        dependency_links=[
        'https://testpypi.python.org/pypi',
        
        ],
      entry_points = {
        "console_scripts": [
            "cbpi=cbpi.cli:main",
        ]
    }
)
