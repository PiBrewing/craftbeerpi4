# -*- coding: utf-8 -*-

# Topic pattern:
# Tasmota on sonoff:
# tasmota on sonoff TH16 or TH10 topic: cmnd/<tasmota_name_of _device>/Power
# or like eg. cmnd/tasmota_F9713B/Power
# Power in the meaning of on/off. Power as % is not supported
# Have a look at https://stevessmarthomeguide.com/setting-up-the-sonoff-tasmota-mqtt-switch/
# In Tasmota adjust configuration-> configure logging->Telemetry period (300) from 300s to 10s
# to speed up the sensor (I know this is the actor section)
# If you need to change payload please edit in function async def on(..) and async def off..)
#
# EspEasy
# use this link:
# https://nerdiy.de/howto-espeasy-mqtt-server-konfigurieren-und-topics-abonnieren/
# You may use translate function of the browser to translate the language
# If you need to change payload please edit in function async def on(..) and async def off..)

import asyncio
import logging
import json
from cbpi.api import *

logger = logging.getLogger(__name__)


@parameters([Property.Text(label="Topic", configurable=True, description="MQTT Topic"),
             Property.Select(label="select_Mqtt_System", options=["default", "tasmota on sonoff THx", "ESPEasy"],
                             description="different Mqtt Systems listen to different payloads")])
class MQTTActor(CBPiActor):

    @action("Set Power",
            parameters=[Property.Number(label="Power", configurable=True, description="Power Setting [0-100]")])
    async def setpower(self, Power=100, **kwargs):
        self.power = int(Power)
        if self.power < 0:
            self.power = 0
        if self.power > 100:
            self.power = 100
        await self.set_power(self.power)

    def __init__(self, cbpi, id, props):
        super(MQTTActor, self).__init__(cbpi, id, props)

    async def on_start(self):
        self.topic = self.props.get("Topic", None)
        self.mqtt_select = self.props.get("select_Mqtt_System", None)
        if self.mqtt_select is None:
            self.mqtt_select = "default"
        pass

        self.power = 100
        logger.info("Mqtt started")

    async def on(self, power=None):
        if power is not None:
            if power != self.power:
                power = min(100, power)
                power = max(0, power)
                self.power = int(power)
        else:
            # just to be safe
            self.power = 0

        if self.mqtt_select == "default":
            await self.cbpi.satellite.publish(self.topic, json.dumps({"state": "on", "power": self.power}), True)
        elif self.mqtt_select == "tasmota on sonoff THx":
            await self.cbpi.satellite.publish(self.topic, "on", True)
        elif self.mqtt_select == "ESPEasy":
            await self.cbpi.satellite.publish(self.topic, 1, True)
        else:
            logger.error("MQTT on: no Mqtt System selected")
        pass
        self.state = True

    async def off(self):
        self.state = False

        if self.mqtt_select == "default":
            await self.cbpi.satellite.publish(self.topic, json.dumps({"state": "off", "power": self.power}), True)
        elif self.mqtt_select == "tasmota on sonoff THx":
            await self.cbpi.satellite.publish(self.topic, "off", True)
        elif self.mqtt_select == "ESPEasy":
            await self.cbpi.satellite.publish(self.topic, 0, True)
        else:
            logger.error("MQTT off: no Mqtt System selected")
            pass

    async def run(self):
        while self.running:
            await asyncio.sleep(1)

    def get_state(self):
        return self.state

    async def set_power(self, power):
        self.power = int(power)
        if self.state is True:
            await self.on(power)
        else:
            await self.off()
        await self.cbpi.actor.actor_update(self.id, power)
        pass


def setup(cbpi):
    '''
    This method is called by the server during startup
    Here you need to register your plugins at the server

    :param cbpi: the cbpi core
    :return:
    '''
    if str(cbpi.static_config.get("mqtt", False)).lower() == "true":
        cbpi.plugin.register("MQTTActor", MQTTActor)
