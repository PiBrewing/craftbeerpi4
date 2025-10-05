import asyncio
import logging
import psutil

from cbpi.api import *
from cbpi.api.base import CBPiBase
from cbpi.api.config import ConfigType
from cbpi.controller.fermentation_controller import FermentationController
from cbpi.controller.kettle_controller import KettleController

logger = logging.getLogger(__name__)


class Systemdata(CBPiExtension):

    def __init__(self, cbpi):
        self.cbpi = cbpi
        self.update_key = "systemupdate"
        self.sorting = False
        self._task = asyncio.create_task(self.run())
        logger.error("INIT Systemdata Extension")

    async def run(self):
        while True:
            mem = psutil.virtual_memory()
            totalmem=round((int(mem.total) / (1024 * 1024)), 1)
            availablemem=round((int(mem.available) / (1024 * 1024)), 1)
            percentmem=round(float(mem.percent), 1)
            self.data=[totalmem,availablemem,percentmem]
            #logging.error("Systemdata: {}".format(self.data))
            self.cbpi.ws.send(
                dict(
                    topic=self.update_key,
                    data=dict(
                    totalmem=totalmem,
                    availablemem=availablemem,
                    percentmem=percentmem,
                    )
                ),self.sorting)
            
            await asyncio.sleep(30)





def setup(cbpi):
    cbpi.plugin.register("Systemdata", Systemdata)
    pass
