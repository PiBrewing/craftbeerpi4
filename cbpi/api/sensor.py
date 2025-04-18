import asyncio
import logging
from abc import ABCMeta, abstractmethod

from cbpi.api.base import CBPiBase
from cbpi.api.dataclasses import DataType
from cbpi.api.extension import CBPiExtension


class CBPiSensor(CBPiBase, metaclass=ABCMeta):

    def __init__(self, cbpi, id, props):
        self.cbpi = cbpi
        self.id = id
        self.props = props
        self.logger = logging.getLogger(__file__)
        self.data_logger = None
        self.state = False
        self.running = False
        self.datatype = DataType.VALUE
        self.inrange = True
        self.temprange = 0
        self.kettle = None
        self.fermenter = None

    def init(self):
        pass

    def log_data(self, value):
        self.cbpi.log.log_data(self.id, value)

    def get_state(self):
        pass

    def get_value(self):
        pass

    def get_unit(self):
        pass

    def checkrange(self, value):
        # if Kettle and fermenter are selected, range check is deactivated
        if self.kettle is not None and self.fermenter is not None:
            return True
        try:
            if self.kettle is not None:
                target_temp = float(self.kettle.target_temp)
            if self.fermenter is not None:
                target_temp = float(self.fermenter.target_temp)

            diff = abs(target_temp - value)
            if diff > self.temprange:
                return False
            else:
                return True
        except Exception as e:
            return True

    def push_update(self, value, mqtt=True):
        if self.temprange != 0:
            self.inrange = self.checkrange(value)
        else:
            self.inrange = True
        try:
            self.cbpi.ws.send(
                dict(
                    topic="sensorstate",
                    id=self.id,
                    value=value,
                    datatype=self.datatype.value,
                    inrange=self.inrange,
                )
            )
            if mqtt:
                self.cbpi.push_update(
                    "cbpi/sensordata/{}".format(self.id),
                    dict(
                        id=self.id,
                        value=value,
                        datatype=self.datatype.value,
                        inrange=self.inrange,
                    ),
                    retain=True,
                )
        #            self.cbpi.push_update("cbpi/sensor/{}/udpate".format(self.id), dict(id=self.id, value=value), retain=True)
        except:
            logging.error("Failed to push sensor update for sensor {}".format(self.id))

    async def start(self):
        pass

    async def stop(self):
        pass

    async def on_start(self):
        pass

    async def on_stop(self):
        pass

    async def run(self):
        pass

    async def _run(self):

        try:
            await self.on_start()
            self.cancel_reason = await self.run()
        except asyncio.CancelledError as e:
            pass
        finally:
            await self.on_stop()
