import asyncio
import logging
import time
from abc import ABCMeta, abstractmethod

from cbpi.api.config import ConfigType


class CBPiBase(metaclass=ABCMeta):

    def get_static_config_value(self, name, default):
        return self.cbpi.static_config.get(name, default)

    def get_config_value(self, name, default):
        return self.cbpi.config.get(name, default=default)

    async def set_config_value(self, name, value):
        return await self.cbpi.config.set(name, value)

    async def remove_config_parameter(self, name):
        return await self.cbpi.config.remove(name)

    async def add_config_value(
        self, name, value, type: ConfigType, description, source, options=None
    ):
        await self.cbpi.config.add(name, value, type, description, source, options=None)

    def get_kettle(self, id):
        return self.cbpi.kettle.find_by_id(id)

    def get_kettle_target_temp(self, id):
        return self.cbpi.kettle.find_by_id(id).target_temp

    async def set_target_temp(self, id, temp):
        await self.cbpi.kettle.set_target_temp(id, temp)

    def get_fermenter(self, id):
        return self.cbpi.fermenter._find_by_id(id)

    def get_fermenter_target_temp(self, id):
        return self.cbpi.fermenter._find_by_id(id).target_temp

    async def set_fermenter_target_temp(self, id, temp):
        await self.cbpi.fermenter.set_target_temp(id, temp)

    def get_fermenter_target_pressure(self, id):
        return self.cbpi.fermenter._find_by_id(id).target_pressure

    async def set_fermenter_target_pressure(self, id, temp):
        await self.cbpi.fermenter.set_target_pressure(id, temp)

    def get_sensor(self, id):
        return self.cbpi.sensor.find_by_id(id)

    def get_sensor_value(self, id):

        return self.cbpi.sensor.get_sensor_value(id)

    def get_sensor_usable_value(self, id):
        """Sensor value as a float, or None when it must not drive control
        (no reading yet, reading timed out, NaN, sensor stopped)."""
        return self.cbpi.sensor.get_usable_value(id)

    async def get_control_value(self, sensor_id, actors, owner):
        """Usable value of sensor_id for a control loop.

        Returns None after switching the given actors off when the sensor has
        no fresh, finite reading: a NaN fails every comparison and a frozen
        value never reaches the target, either of which left a heater or a
        cooler running indefinitely. Notifies once when the reading is lost and
        once when it comes back.
        """
        from cbpi.api.dataclasses import NotificationType

        value = self.get_sensor_usable_value(sensor_id)
        # tracked per sensor: a logic reading two sensors (mash tun and RIMS,
        # beer and chamber) would otherwise notify lost/back on every loop
        if not hasattr(self, "_control_value_lost"):
            self._control_value_lost = set()
        lost_sensors = self._control_value_lost
        lost = sensor_id in lost_sensors
        if value is None:
            for actor in actors:
                if actor:
                    await self.actor_off(actor)
            if not lost:
                lost_sensors.add(sensor_id)
                sensor = self.cbpi.sensor.find_by_id(sensor_id)
                name = sensor.name if sensor is not None else sensor_id
                logging.warning(
                    "{}: no usable value from sensor {}, actors switched off".format(owner, name)
                )
                self.cbpi.notify(
                    owner,
                    "No usable reading from sensor '{}' (no data, timed out or invalid). Heating/cooling is switched off until it comes back.".format(name),
                    NotificationType.ERROR,
                )
        elif lost:
            lost_sensors.discard(sensor_id)
            self.cbpi.notify(owner, "Sensor reading is back, control resumed.", NotificationType.INFO)
        return value

    def get_actor(self, id):
        return self.cbpi.actor.find_by_id(id)

    def get_actor_state(self, id):
        try:
            actor = self.cbpi.actor.find_by_id(id)
            return actor.instance.state
        except:
            logging.error("Failed to read actor state in step - actor {}".format(id))
            return False

    async def actor_on(self, id, power=100, output=None):

        try:
            await self.cbpi.actor.on(id, power, output)
        except Exception as e:
            pass

    async def actor_off(self, id):
        try:
            await self.cbpi.actor.off(id)
        except Exception as e:
            pass

    async def actor_set_power(self, id, power):
        try:
            await self.cbpi.actor.set_power(id, power)
        except Exception as e:
            pass

    async def actor_set_output(self, id, output):
        try:
            await self.cbpi.actor.set_output(id, output)
        except Exception as e:
            pass
