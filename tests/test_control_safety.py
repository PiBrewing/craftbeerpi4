import asyncio
import math
import unittest
from types import SimpleNamespace

from cbpi.api.dataclasses import NotificationType, Props, Step
from cbpi.api.kettle_logic import CBPiKettleLogic
from cbpi.api.sensor import CBPiSensor
from cbpi.api.dataclasses import Fermenter
from cbpi.api.step import CBPiFermentationStep, CBPiStep, StepResult, StepState
from cbpi.api.timer import Timer
from cbpi.controller.satellite_controller import SatelliteController
from cbpi.extension.hysteresis import Hysteresis
from tests.cbpi_config_fixture import CraftBeerPiTestCase


class FakeCbpi:
    """Just enough of CraftBeerPi for sensors, logics and the satellite."""

    def __init__(self):
        self.notifications = []
        self.switched_off = []
        self.switched_on = []
        self.sensors = {}
        self.kettles = {}
        self.ws = SimpleNamespace(send=lambda *a, **k: None)
        self.static_config = {}
        self.sensor = SimpleNamespace(
            find_by_id=lambda id: self.sensors.get(id),
            get_usable_value=lambda id: (
                self.sensors[id].instance.usable_value() if id in self.sensors else None
            ),
        )
        self.kettle = SimpleNamespace(
            find_by_id=lambda id: self.kettles.get(id), push_udpate=self._noop
        )
        self.actor = SimpleNamespace(
            find_by_id=lambda id: None, on=self._actor_on, off=self._actor_off
        )
        for name in ("fermenter", "satellite"):
            setattr(self, name, None)

    async def _noop(self, *args, **kwargs):
        pass

    async def _actor_on(self, id, power=None, output=None):
        self.switched_on.append(id)

    async def _actor_off(self, id):
        self.switched_off.append(id)

    def notify(self, title, message, type=NotificationType.INFO, action=[]):
        self.notifications.append((title, message, type))

    def push_update(self, *args, **kwargs):
        pass


class FakeSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.value = 0

    def get_state(self):
        return dict(value=self.value)


def add_sensor(cbpi, id, stale_after=None):
    sensor = FakeSensor(cbpi, id, Props({}))
    sensor.stale_after = stale_after
    cbpi.sensors[id] = SimpleNamespace(id=id, name=id, instance=sensor)
    return sensor


class TimerTest(unittest.IsolatedAsyncioTestCase):

    async def test_stop_does_not_fire_on_done(self):
        fired = []

        async def on_done(timer):
            fired.append(timer)

        timer = Timer(60, on_done=on_done)
        timer.start()
        await asyncio.sleep(0.05)
        await timer.stop()
        await asyncio.sleep(0.05)
        # pausing a step used to run on_done, which moved to the next step
        self.assertEqual(fired, [])

    async def test_expiry_fires_on_done(self):
        fired = []

        async def on_done(timer):
            fired.append(timer)

        timer = Timer(0, on_done=on_done)
        timer.start()
        await asyncio.sleep(0.05)
        self.assertEqual(len(fired), 1)


class SensorUsableValueTest(unittest.TestCase):

    def test_nan_is_not_usable(self):
        cbpi = FakeCbpi()
        sensor = add_sensor(cbpi, "s")
        sensor.value = float("nan")
        sensor.push_update(sensor.value)
        self.assertIsNone(sensor.usable_value())
        sensor.value = "nan"
        self.assertIsNone(sensor.usable_value())

    def test_sensor_without_staleness_is_usable(self):
        cbpi = FakeCbpi()
        sensor = add_sensor(cbpi, "s")
        sensor.value = 21.5
        self.assertEqual(sensor.usable_value(), 21.5)

    def test_initial_value_is_not_a_reading(self):
        cbpi = FakeCbpi()
        sensor = add_sensor(cbpi, "s", stale_after=math.inf)
        sensor.value = 999
        self.assertIsNone(sensor.usable_value())
        sensor.value = 20.0
        sensor.push_update(sensor.value)
        self.assertEqual(sensor.usable_value(), 20.0)

    def test_old_reading_expires(self):
        cbpi = FakeCbpi()
        sensor = add_sensor(cbpi, "s", stale_after=60)
        sensor.value = 20.0
        sensor.push_update(sensor.value)
        self.assertEqual(sensor.usable_value(), 20.0)
        sensor.value_time -= 61
        self.assertIsNone(sensor.usable_value())

    def test_failed_sensor_is_not_usable(self):
        cbpi = FakeCbpi()
        sensor = add_sensor(cbpi, "s")
        sensor.value = 20.0
        sensor.failed = True
        self.assertIsNone(sensor.usable_value())


class SensorCrashTest(unittest.IsolatedAsyncioTestCase):

    async def test_crash_notifies_and_invalidates(self):
        class Crashing(FakeSensor):
            async def run(self):
                raise RuntimeError("bus error")

        cbpi = FakeCbpi()
        sensor = Crashing(cbpi, "s", Props({}))
        cbpi.sensors["s"] = SimpleNamespace(id="s", name="probe", instance=sensor)
        sensor.value = 20.0
        await sensor._run()
        self.assertIsNone(sensor.usable_value())
        self.assertEqual(cbpi.notifications[0][2], NotificationType.ERROR)
        self.assertIn("probe", cbpi.notifications[0][1])


class MQTTSensorNaNTest(unittest.IsolatedAsyncioTestCase):

    async def test_nan_is_logged_once_per_loss(self):
        from cbpi.extension.mqtt_sensor import MQTTSensor

        sensor = MQTTSensor.__new__(MQTTSensor)
        sensor.cbpi = FakeCbpi()
        sensor.id = "s"
        sensor.sensor = SimpleNamespace(name="ferm")
        sensor.payload_text = None
        sensor.value = 999
        sensor.value_time = None
        sensor.temprange = 0
        sensor.ignoring_invalid = False
        sensor.reducedlogging = False
        sensor.timeout = 0
        sensor.log_data = lambda value: None

        def message(payload):
            return SimpleNamespace(payload=payload.encode())

        with self.assertLogs(level="WARNING") as logs:
            for _ in range(5):
                await sensor.on_message(message("NaN"))
            await sensor.on_message(message("12.5"))
            await sensor.on_message(message("12.6"))
            await sensor.on_message(message("NaN"))
        # an ESP publishes nan every few seconds while its probe is unplugged
        messages = [r.getMessage() for r in logs.records if "MQTTSensor" in r.getMessage()]
        self.assertEqual(
            messages,
            [
                "MQTTSensor ferm ignored non-numeric value nan",
                "MQTTSensor ferm receives numeric values again",
                "MQTTSensor ferm ignored non-numeric value nan",
            ],
        )
        self.assertEqual(sensor.value, 12.6)


class HysteresisFailSafeTest(unittest.IsolatedAsyncioTestCase):

    def make_logic(self, cbpi, sensor):
        kettle = SimpleNamespace(
            id="k", name="HLT", sensor="s", heater="heater", agitator=None,
            target_temp=70, instance=None,
        )
        cbpi.kettles["k"] = kettle
        logic = Hysteresis(cbpi, "k", Props({"OffsetOn": 1, "OffsetOff": 0}))
        logic.running = True
        logic.state = True
        return logic

    async def run_for(self, logic, seconds):
        task = asyncio.create_task(logic._run())
        await asyncio.sleep(seconds)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def test_nan_switches_heater_off(self):
        cbpi = FakeCbpi()
        sensor = add_sensor(cbpi, "s", stale_after=math.inf)
        sensor.value = float("nan")
        logic = self.make_logic(cbpi, sensor)
        await self.run_for(logic, 0.1)
        # a NaN used to fail both comparisons and leave the heater as it was
        self.assertIn("heater", cbpi.switched_off)
        self.assertNotIn("heater", cbpi.switched_on)
        errors = [n for n in cbpi.notifications if n[2] == NotificationType.ERROR]
        self.assertEqual(len(errors), 1)

    async def test_fresh_reading_heats(self):
        cbpi = FakeCbpi()
        sensor = add_sensor(cbpi, "s", stale_after=math.inf)
        sensor.value = 20.0
        sensor.push_update(sensor.value)
        logic = self.make_logic(cbpi, sensor)
        await self.run_for(logic, 0.1)
        self.assertIn("heater", cbpi.switched_on)
        self.assertEqual(cbpi.notifications, [])

    async def test_two_sensors_lost_and_back_notify_once_each(self):
        cbpi = FakeCbpi()
        mash = add_sensor(cbpi, "mash", stale_after=math.inf)
        rims = add_sensor(cbpi, "rims", stale_after=math.inf)
        mash.value = 65.0
        mash.push_update(mash.value)
        logic = self.make_logic(cbpi, mash)
        # a logic reading two sensors, one of them without a reading: the
        # lost state is per sensor, so the good one must not clear it
        for _ in range(3):
            self.assertEqual(await logic.get_control_value("mash", ["heater"], "HLT"), 65.0)
            self.assertIsNone(await logic.get_control_value("rims", ["heater"], "HLT"))
        self.assertEqual([n[2] for n in cbpi.notifications], [NotificationType.ERROR])
        rims.value = 70.0
        rims.push_update(rims.value)
        for _ in range(3):
            await logic.get_control_value("mash", ["heater"], "HLT")
            await logic.get_control_value("rims", ["heater"], "HLT")
        self.assertEqual(
            [n[2] for n in cbpi.notifications],
            [NotificationType.ERROR, NotificationType.INFO],
        )

    async def test_logic_crash_switches_off_and_notifies(self):
        class Crashing(CBPiKettleLogic):
            async def run(self):
                raise RuntimeError("boom")

        cbpi = FakeCbpi()
        cbpi.kettles["k"] = SimpleNamespace(
            id="k", name="HLT", heater="heater", agitator="stirrer"
        )
        logic = Crashing(cbpi, "k", Props({}))
        logic.running = True
        logic.state = True
        await logic._run()
        self.assertFalse(logic.state)
        self.assertEqual(sorted(cbpi.switched_off), ["heater", "stirrer"])
        self.assertEqual(cbpi.notifications[0][2], NotificationType.ERROR)


class FakeMqttClient:
    def __init__(self):
        self.published = []
        self.fail = False

    async def publish(self, topic, message, qos=0, retain=False):
        if self.fail:
            import aiomqtt

            raise aiomqtt.MqttError("broker gone")
        self.published.append((topic, message, retain))


class SatelliteResendTest(unittest.IsolatedAsyncioTestCase):

    def make(self):
        cbpi = FakeCbpi()
        cbpi.kettle = cbpi.fermenter = cbpi.sensor = cbpi.actor = None
        satellite = SatelliteController(cbpi)
        satellite.client = FakeMqttClient()
        return satellite

    async def test_off_sent_while_disconnected_is_resent(self):
        satellite = self.make()
        satellite.connected = False
        await satellite.publish("relay", '{"state": "on"}', True)
        await satellite.publish("relay", '{"state": "off"}', True)
        self.assertEqual(satellite.client.published, [])
        satellite.connected = True
        await satellite._flush_pending()
        # only the latest state is re-sent, retained
        self.assertEqual(satellite.client.published, [("relay", '{"state": "off"}', True)])
        self.assertEqual(satellite.pending, {})

    async def test_failed_publish_is_resent(self):
        satellite = self.make()
        satellite.connected = True
        satellite.client.fail = True
        await satellite.publish("relay", '{"state": "off"}', True)
        satellite.client.fail = False
        await satellite._flush_pending()
        self.assertEqual(satellite.client.published, [("relay", '{"state": "off"}', True)])

    async def test_newer_state_supersedes_pending(self):
        satellite = self.make()
        satellite.connected = True
        satellite.client.fail = True
        await satellite.publish("relay", '{"state": "on"}', True)
        satellite.client.fail = False
        await satellite.publish("relay", '{"state": "off"}', True)
        await satellite._flush_pending()
        self.assertEqual(satellite.client.published, [("relay", '{"state": "off"}', True)])

    async def test_non_retained_is_not_queued(self):
        satellite = self.make()
        satellite.connected = False
        await satellite.publish("cbpi/sensordata/x", "1", False)
        self.assertEqual(satellite.pending, {})


class LongStep(CBPiStep):
    instances = []

    async def on_start(self):
        LongStep.instances.append(self)

    async def run(self):
        while self.running:
            await asyncio.sleep(0.01)
        return StepResult.DONE


class StepEditTestCase(CraftBeerPiTestCase):

    async def test_editing_active_step_leaves_no_orphan(self):
        controller = self.cbpi.step
        controller.types["LongStep"] = {"class": LongStep}
        LongStep.instances = []
        step = await controller.add(Step(name="Rest", props=Props({}), type="LongStep"))
        try:
            await controller.start_step(step)
            await asyncio.sleep(0.05)
            old_instance = step.instance

            edited = Step(step.id, "Rest edited", Props({}), "LongStep")
            await controller.update(edited)
            await asyncio.sleep(0.05)

            # the old instance used to keep running next to the new one
            self.assertTrue(old_instance.task.done())
            self.assertEqual(controller.find_by_id(step.id).status, StepState.ACTIVE)
            running = [i for i in LongStep.instances if not i.task.done()]
            self.assertEqual(running, [edited.instance])
        finally:
            await controller.find_by_id(step.id).instance.stop()
            controller.find_by_id(step.id).status = StepState.INITIAL
            await controller.delete(step.id)


class LongFermentationStep(CBPiFermentationStep):
    instances = []

    async def on_start(self):
        LongFermentationStep.instances.append(self)

    async def run(self):
        while self.running:
            await asyncio.sleep(0.01)
        return StepResult.DONE


class FermenterStepEditTestCase(CraftBeerPiTestCase):

    async def test_editing_active_step_keeps_timer_and_leaves_no_orphan(self):
        controller = self.cbpi.fermenter
        controller.steptypes["LongFermentationStep"] = {"class": LongFermentationStep}
        LongFermentationStep.instances = []
        fermenter = await controller.create(Fermenter(name="FV1"))
        try:
            step = await controller.add_step(
                fermenter.id,
                {"name": "Primary", "type": "LongFermentationStep", "endtime": 0, "props": {"TimerD": 7}},
            )
            await controller.start(fermenter.id)
            await asyncio.sleep(0.05)
            step.endtime = 1_000_000
            old_instance = step.instance

            # what the GUI sends: no status, endtime 0
            await controller.update_step(
                fermenter.id,
                {"id": step.id, "name": "Primary", "endtime": 0,
                 "type": "LongFermentationStep", "props": {"TimerD": 8}},
            )
            await asyncio.sleep(0.05)

            edited = controller._find_step_by_id(fermenter.steps, step.id)
            self.assertTrue(old_instance.task.done())
            self.assertEqual(edited.status, StepState.ACTIVE)
            # the running timer is kept, shifted by the extra day
            self.assertEqual(edited.endtime, 1_000_000 + 86400)
            running = [i for i in LongFermentationStep.instances if not i.task.done()]
            self.assertEqual(running, [edited.instance])
        finally:
            await controller.delete(fermenter.id)


class ActorDeleteTestCase(CraftBeerPiTestCase):

    async def test_deleting_an_actor_switches_it_off(self):
        resp = await self.client.post(
            path="/actor/", json={"name": "relay", "type": "DummyActor", "props": {}}
        )
        assert resp.status == 200
        actor_id = (await resp.json())["id"]
        await self.cbpi.actor.on(actor_id)
        instance = self.cbpi.actor.find_by_id(actor_id).instance
        self.assertTrue(instance.state)

        resp = await self.client.delete(path="/actor/%s" % actor_id)
        assert resp.status == 200
        # deleting used to only end the actor loop, leaving the output on
        self.assertFalse(instance.state)


if __name__ == "__main__":
    unittest.main()
