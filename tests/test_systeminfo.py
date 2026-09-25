import asyncio
import os
import tempfile
import time
from unittest import mock

from cbpi.controller import system_controller
from cbpi.controller.system_controller import SystemController
from tests.cbpi_config_fixture import CraftBeerPiTestCase


def fake_hwmon(root, devices):
    paths = []
    for i, (name, millidegrees) in enumerate(devices):
        path = os.path.join(root, "hwmon%d" % i)
        os.makedirs(path)
        with open(os.path.join(path, "name"), "w") as f:
            f.write(name + "\n")
        with open(os.path.join(path, "temp1_input"), "w") as f:
            f.write("%d\n" % millidegrees)
        paths.append(path)
    return paths


class SystemInfoTestCase(CraftBeerPiTestCase):

    async def test_endpoint(self):
        resp = await self.client.get(path="/system/systeminfo")
        assert resp.status == 200
        data = await resp.json()
        assert "temp" in data and "cpuload" in data

    async def test_cpu_temperature_ignores_other_hwmon(self):
        with tempfile.TemporaryDirectory() as root:
            # 1-wire probes listed first: they must not be picked
            paths = fake_hwmon(root, [("w1_slave_temp", 19000), ("w1_slave_temp", 64000), ("cpu_thermal", 55500)])
            with mock.patch.object(system_controller.glob, "glob", return_value=paths):
                assert SystemController._cpu_temperature(False) == 55.5
                assert SystemController._cpu_temperature(True) == 131.9

    async def test_cpu_temperature_missing(self):
        with tempfile.TemporaryDirectory() as root:
            paths = fake_hwmon(root, [("w1_slave_temp", 19000)])
            with mock.patch.object(system_controller.glob, "glob", return_value=paths):
                assert SystemController._cpu_temperature(False) == 0

    async def test_slow_systeminfo_does_not_block_the_loop(self):
        real = self.cbpi.system._systeminfo

        def slow(unit):
            time.sleep(1.5)
            return real(unit)

        with mock.patch.object(self.cbpi.system, "_systeminfo", side_effect=slow):
            task = asyncio.create_task(self.cbpi.system.systeminfo())
            start = time.monotonic()
            await asyncio.sleep(0.1)
            # the loop kept running while systeminfo was busy
            assert time.monotonic() - start < 0.5
            assert not task.done()
            info = await task
        assert "temp" in info
