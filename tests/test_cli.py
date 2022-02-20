import logging
import unittest
from cbpi.cli import CraftBeerPiCli

from cbpi.configFolder import ConfigFolder

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

class CLITest(unittest.TestCase):

    def test_install(self):
        cli = CraftBeerPiCli(ConfigFolder("./cbpi-test-config"))
        cli.plugins_add("cbpi4-ui-plugin")
        cli.plugins_add("cbpi4-ui-plugin")
        cli.plugin_remove("cbpi4-ui-plugin")

    def test_list(self):
        cli = CraftBeerPiCli(ConfigFolder("./cbpi-test-config"))
        cli.plugins_list()

if __name__ == '__main__':
    unittest.main()