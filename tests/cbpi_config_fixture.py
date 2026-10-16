# content of conftest.py
import os
import shutil
import tempfile
from cbpi.configFolder import ConfigFolder
from cbpi.craftbeerpi import CraftBeerPi
from aiohttp.test_utils import AioHTTPTestCase


class CraftBeerPiTestCase(AioHTTPTestCase):

    async def get_application(self):
        self.config_folder = self.configuration()
        self.cbpi = CraftBeerPi(self.config_folder)
        await self.cbpi.init_serivces()
        return self.cbpi.app

    def configuration(self):
        # Each test runs on its own copy of the test config, so a test never
        # sees what an earlier one wrote and the run leaves the repository
        # untouched (cbpi rewrites config.json with its version at startup).
        test_directory = os.path.dirname(__file__)
        self.temp_directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_directory, ignore_errors=True)
        test_config_directory = os.path.join(self.temp_directory, 'config')
        shutil.copytree(os.path.join(test_directory, 'cbpi-test-config'), test_config_directory)
        test_logs_directory = os.path.join(self.temp_directory, 'logs')
        os.mkdir(test_logs_directory)
        configFolder = ConfigFolder(test_config_directory, test_logs_directory)
        return configFolder
