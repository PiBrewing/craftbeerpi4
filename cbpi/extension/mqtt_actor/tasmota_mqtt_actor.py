from cbpi.api import Property, parameters

from . import GenericMqttActor


@parameters(
    [
        Property.Text(label="Topic", configurable=True, description="MQTT Topic"),
    ]
)
class TasmotaMqttActor(GenericMqttActor):
    def __init__(self, cbpi, id, props):
        GenericMqttActor.__init__(self, cbpi, id, props)

    async def on_start(self):
        await GenericMqttActor.on_start(self)
        self.payload = "{switch_onoff}"
