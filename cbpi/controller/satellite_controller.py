import asyncio
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from re import M

import shortuuid
import aiomqtt
from cbpi import __version__



class SatelliteController:

    def __init__(self, cbpi):
        self.client_id = shortuuid.uuid()
        self.cbpi = cbpi
        self.kettlecontroller = cbpi.kettle
        self.fermentercontroller = cbpi.fermenter
        self.sensorcontroller = cbpi.sensor
        self.actorcontroller = cbpi.actor
        self.logger = logging.getLogger(__name__)
        self.host = cbpi.static_config.get("mqtt_host", "localhost")
        self.port = cbpi.static_config.get("mqtt_port", 1883)
        self.username = cbpi.static_config.get("mqtt_username", None)
        self.password = cbpi.static_config.get("mqtt_password", None)
        self.client = None
        self.topic_filters = [
            ("cbpi/actor/+/on", self._actor_on),
            ("cbpi/actor/+/off", self._actor_off),
            ("cbpi/actor/+/power", self._actor_power),
            ("cbpi/actor/+/output", self._actor_output),
            ("cbpi/updateactor", self._actorupdate),
            ("cbpi/updatekettle", self._kettleupdate),
            ("cbpi/updatesensor", self._sensorupdate),
            ("cbpi/updatefermenter", self._fermenterupdate),
        ]
        self.tasks = set()
        self.connected = False
        # Latest retained message per topic that could not be delivered. Actor
        # states are retained: an "off" published while the broker was away was
        # dropped, cbpi showed the actor off and the relay stayed on. They are
        # re-sent as soon as the connection is back.
        self.pending = {}
        self.publish_seq = {}

    def remove_key(self, d, key):
        r = dict(d)
        del r[key]
        return r

    async def init(self):

        self.client = aiomqtt.Client(          
            self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            will=aiomqtt.Will(topic="cbpi/disconnect", payload="CBPi Server Disconnected"),
            identifier=self.client_id,
        )
        try:
            ## Listen for mqtt messages in an (unawaited) asyncio task
            task = asyncio.create_task(self.listen())
            ## Save a reference to the task so it doesn't get garbage collected
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            self.logger.info("MQTT Connected to {}:{}".format(self.host, self.port))
        except asyncio.CancelledError as e:
            self.logger.error("MQTT Connection failed: {}".format(e))

    async def listen(self):
        while True:
            try:
                async with self.client as client:
                    await client.subscribe("#")
                    self.connected = True
                    await self._flush_pending()
                    async for message in client.messages:
                        for topic_filter in self.topic_filters:
                            topic = topic_filter[0]
                            method = topic_filter[1]
                            if message.topic.matches(topic):
                                await method(message)
            except asyncio.CancelledError:
                # Cancel
                self.logger.warning("MQTT Listening Cancelled")
                break
            except aiomqtt.MqttError as e:
                self.logger.warning("MQTT disconnected: {}. Reconnecting in 5s".format(e))
            except Exception as e:
                self.logger.error("MQTT General Exception: {}. Reconnecting in 5s".format(e))
            finally:
                self.connected = False

            await asyncio.sleep(5)

    async def _flush_pending(self):
        for topic, message in list(self.pending.items()):
            if self.pending.get(topic) is not message:
                continue  # superseded while re-sending the previous ones
            self.logger.info("Re-sending retained MQTT message on {}".format(topic))
            await self.publish(topic, message, retain=True)

    async def publish(self, topic, message, retain=False):
        if retain:
            # only the latest message of a topic may end up pending, so an older
            # state can never be re-sent over a newer one
            seq = self.publish_seq.get(topic, 0) + 1
            self.publish_seq[topic] = seq
        if self.client is None or not self.connected:
            if retain:
                self.pending[topic] = message
            return
        try:
            await self.client.publish(topic, message, qos=1, retain=retain)
            if retain and self.publish_seq[topic] == seq:
                self.pending.pop(topic, None)
        except aiomqtt.MqttError as e:
            self.logger.warning("Failed to push data via mqtt: {}".format(e))
            if retain and self.publish_seq[topic] == seq:
                self.pending[topic] = message

    async def _actor_on(self, message):
        try:
            topic_key = str(message.topic).split("/")
            await self.cbpi.actor.on(topic_key[2])
            self.logger.warning("Processed actor {} on via mqtt".format(topic_key[2]))
        except Exception as e:
            self.logger.warning("Failed to process actor on via mqtt: {}".format(e))

    async def _actor_off(self, message):
        try:
            topic_key = str(message.topic).split("/")
            await self.cbpi.actor.off(topic_key[2])
            self.logger.warning("Processed actor {} off via mqtt".format(topic_key[2]))
        except Exception as e:
            self.logger.warning("Failed to process actor off via mqtt: {}".format(e))

    async def _actor_power(self, message):
        try:
            topic_key = str(message.topic).split("/")
            try:
                power = int(message.payload.decode())
                if power > 100:
                    power = 100
                if power < 0:
                    power = 0
                await self.cbpi.actor.set_power(topic_key[2], power)
                # await self.cbpi.actor.actor_update(topic_key[2],power)
            except:
                self.logger.warning(
                    "Failed to set actor power via mqtt. No valid power in message"
                )
        except:
            self.logger.warning("Failed to set actor power via mqtt")

    async def _actor_output(self, message):
        try:
            topic_key = str(message.topic).split("/")
            try:
                output = int(message.payload.decode())
                # if power > 100:
                #    power = 100
                # if power < 0:
                #    power = 0
                await self.cbpi.actor.set_output(topic_key[2], output)
            except:
                self.logger.warning(
                    "Failed to set actor output via mqtt. No valid output in message"
                )
        except:
            self.logger.warning("Failed to set actor output via mqtt")

    async def _kettleupdate(self, message):
        try:
            self.kettle = self.kettlecontroller.get_state()
            for item in self.kettle["data"]:
                self.cbpi.push_update(
                    "cbpi/{}/{}".format("kettleupdate", item["id"]), item
                )
        except Exception as e:
            self.logger.warning("Failed to send kettleupdate via mqtt: {}".format(e))

    async def _fermenterupdate(self, message):
        try:
            self.fermenter = self.fermentercontroller.get_state()
            for item in self.fermenter["data"]:
                item_new = self.remove_key(item, "steps")
                self.cbpi.push_update(
                    "cbpi/{}/{}".format("fermenterupdate", item["id"]), item_new
                )
        except Exception as e:
            self.logger.warning("Failed to send fermenterupdate via mqtt: {}".format(e))

    async def _actorupdate(self, message):
        try:
            self.actor = self.actorcontroller.get_state()
            for item in self.actor["data"]:
                self.cbpi.push_update(
                    "cbpi/{}/{}".format("actorupdate", item["id"]), item
                )
        except Exception as e:
            self.logger.warning("Failed to send actorupdate via mqtt: {}".format(e))

    async def _sensorupdate(self, message):
        try:
            self.sensor = self.sensorcontroller.get_state()
            for item in self.sensor["data"]:
                self.cbpi.push_update(
                    "cbpi/{}/{}".format("sensorupdate", item["id"]), item
                )
        except Exception as e:
            self.logger.warning("Failed to send sensorupdate via mqtt: {}".format(e))

    def subscribe(self, topic, method):
        self.topic_filters.append((topic, method))
        return True

    def unsubscribe(self, topic, method):
        self.topic_filters.remove((topic, method))
        return True
