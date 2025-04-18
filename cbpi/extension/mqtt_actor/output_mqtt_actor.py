import asyncio
import json
from cbpi.api import parameters, Property, CBPiActor
from cbpi.api import *
import logging


@parameters(
    [
        Property.Text(label="Topic", configurable=True, description="MQTT Topic"),
        Property.Number(
            label="MaxOutput", configurable=True, description="Max Output Value"
        ),
    ]
)
class OutputMQTTActor(CBPiActor):

    # Custom property which can be configured by the user
    @action(
        "Set Power",
        parameters=[
            Property.Number(
                label="Power", configurable=True, description="Power Setting [0-100]"
            )
        ],
    )
    async def setpower(self, Power=100, **kwargs):
        self.power = int(Power)
        if self.power < 0:
            self.power = 0
        if self.power > 100:
            self.power = 100
        self.output = round(self.maxoutput * self.power / 100)
        await self.set_power(self.power)

    @action(
        "Set Output",
        parameters=[
            Property.Number(
                label="Output",
                configurable=True,
                description="Output Setting [0-MaxOutput]",
            )
        ],
    )
    async def setoutput(self, Output=100, **kwargs):
        self.output = int(Output)
        if self.output < 0:
            self.output = 0
        if self.output > self.maxoutput:
            self.output = self.maxoutput
        await self.set_output(self.output)

    def __init__(self, cbpi, id, props):
        super(OutputMQTTActor, self).__init__(cbpi, id, props)

    async def on_start(self):
        self.topic = self.props.get("Topic", None)
        self.power = 100
        self.maxoutput = int(self.props.get("MaxOutput", 100))
        self.output = self.maxoutput
        await self.cbpi.actor.actor_update(
            self.id, self.power, self.output, self.maxoutput
        )
        await self.off()
        self.state = False

    async def on(self, power=None, output=None):
        if power is not None:
            if power != self.power:
                power = min(100, power)
                power = max(0, power)
                self.power = round(power)
        if output is not None:
            if output != self.output:
                output = min(self.maxoutput, output)
                output = max(0, output)
                self.output = round(output)
        await self.cbpi.satellite.publish(
            self.topic,
            json.dumps({"state": "on", "power": self.power, "output": self.output}),
            True,
        )
        self.state = True
        pass

    async def off(self):
        self.state = False
        await self.cbpi.satellite.publish(
            self.topic, json.dumps({"state": "off", "power": 0, "output": 0}), True
        )
        pass

    async def run(self):
        while self.running:
            await asyncio.sleep(1)

    def get_state(self):
        return self.state

    async def set_power(self, power):
        self.power = round(power)
        self.output = round(self.maxoutput * self.power / 100)
        if self.state == True:
            await self.on(power, self.output)
        else:
            await self.off()
        await self.cbpi.actor.actor_update(self.id, power, self.output)
        pass

    async def set_output(self, output):
        self.output = round(output)
        self.power = round(self.output / self.maxoutput * 100)
        if self.state == True:
            await self.on(self.power, self.output)
        else:
            await self.off()
        await self.cbpi.actor.actor_update(self.id, self.power, self.output)
        pass
