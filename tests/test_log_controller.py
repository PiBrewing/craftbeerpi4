from tests.cbpi_config_fixture import CraftBeerPiTestCase


class LogControllerTestCase(CraftBeerPiTestCase):

    async def test_remove_sensor_data_listener(self):
        async def listener(cbpi, id, value, formatted_time, name):
            pass

        listener_id = self.cbpi.log.add_sensor_data_listener(listener)
        self.cbpi.log.remove_sensor_data_listener(listener_id)
        assert listener_id not in self.cbpi.log.sensor_data_listeners
