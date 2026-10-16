import os

from tests.cbpi_config_fixture import CraftBeerPiTestCase


class LogControllerTestCase(CraftBeerPiTestCase):

    def write_log(self, name, lines):
        os.makedirs(self.cbpi.log.logsFolderPath, exist_ok=True)
        path = os.path.join(self.cbpi.log.logsFolderPath, f"sensor_{name}.log")
        with open(path, "w") as file:
            file.write("".join(f"{line}\n" for line in lines))
        self.addCleanup(os.remove, path)

    async def test_get_data_of_a_sensor_without_log(self):
        data = await self.cbpi.log.get_data("test_log_never_written")
        assert data == {"time": [], "test_log_never_written": []}

    async def test_get_data_skips_sensors_without_log(self):
        self.write_log("test_log_a", ["2026-10-16 10:00:00,1", "2026-10-16 10:01:00,2"])
        data = await self.cbpi.log.get_data(["test_log_a", "test_log_never_written"])
        assert len(data["time"]) == 2
        assert data["test_log_a"] == [1, 2]
        assert data["test_log_never_written"] == [None, None]

    async def test_get_data_aligns_times_and_values(self):
        # b has a minute that a has not: every list must cover the same times
        self.write_log("test_log_a", ["2026-10-16 10:00:00,1", "2026-10-16 10:01:00,2"])
        self.write_log("test_log_b", ["2026-10-16 10:00:00,5", "2026-10-16 10:02:00,7"])
        data = await self.cbpi.log.get_data(["test_log_a", "test_log_b"])
        assert len(data["time"]) == 3
        assert len(data["test_log_a"]) == 3
        assert len(data["test_log_b"]) == 3

    async def test_remove_sensor_data_listener(self):
        async def listener(cbpi, id, value, formatted_time, name):
            pass

        listener_id = self.cbpi.log.add_sensor_data_listener(listener)
        self.cbpi.log.remove_sensor_data_listener(listener_id)
        assert listener_id not in self.cbpi.log.sensor_data_listeners
