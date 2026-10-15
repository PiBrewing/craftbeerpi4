import asyncio
import logging
import math
import time
from abc import ABCMeta, abstractmethod

from cbpi.api.base import CBPiBase
from cbpi.api.dataclasses import DataType, NotificationType
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
        # Control logic must not act on a reading that no longer reflects the
        # process: value_time is the monotonic time of the last finite reading
        # pushed, and a sensor that sets stale_after (seconds, math.inf for
        # "needs a first reading but never expires") has no usable value
        # before its first reading or once it is older than that.
        self.value_time = None
        self.stale_after = None
        self.failed = False

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

    @staticmethod
    def is_finite_number(value):
        try:
            return math.isfinite(float(value))
        except (TypeError, ValueError):
            return False

    def usable_value(self):
        """The current value as a float if control logic may act on it, else None."""
        if self.failed:
            return None
        try:
            value = (self.get_state() or {}).get("value")
        except Exception:
            return None
        if not self.is_finite_number(value):
            return None
        if self.stale_after is not None:
            if self.value_time is None:
                return None
            if time.monotonic() - self.value_time > self.stale_after:
                return None
        return float(value)

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
        if self.is_finite_number(value):
            self.value_time = time.monotonic()
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
        except Exception as e:
            # a dead sensor loop used to leave its last value in place forever
            self.failed = True
            self.running = False
            logging.exception("Sensor {} stopped on an error".format(self.id))
            item = self.cbpi.sensor.find_by_id(self.id)
            self.cbpi.notify(
                "Sensor stopped",
                "Sensor '{}' stopped on an error: {}. Its value is no longer used for control.".format(
                    item.name if item is not None else self.id, e
                ),
                NotificationType.ERROR,
            )
        finally:
            await self.on_stop()
