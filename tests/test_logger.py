import asyncio
import glob
import time
from unittest import mock

from tests.cbpi_config_fixture import CraftBeerPiTestCase
import os

class LoggerTestCase(CraftBeerPiTestCase):

    async def test_log_data(self):

        log_name = "unconfigured_test_sensor_ID"
        #clear all logs
        self.cbpi.log.clear_log(log_name)
        assert len(glob.glob(os.path.join(self.cbpi.log.logsFolderPath, f"sensor_{log_name}.log*"))) == 0

        # write log entries, one second apart on a fake clock instead of
        # waiting a real second between them
        start = time.time()
        for i in range(5):
            with mock.patch("cbpi.controller.log_file_controller.localtime",
                            return_value=time.localtime(start + i)):
                self.cbpi.log.log_data(log_name, 222)
            # let the listener tasks write the entry
            for _ in range(3):
                await asyncio.sleep(0)

        # read log data
        data = await self.cbpi.log.get_data(log_name, sample_rate='1s')
        assert len(data["time"]) == 5

        assert self.cbpi.log.zip_log_data(log_name) is not None

        self.cbpi.log.clear_zip(log_name)

        self.cbpi.log.clear_log(log_name)
