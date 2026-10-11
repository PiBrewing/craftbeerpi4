import asyncio
import time

from cbpi.eventlog import EventLog
from tests.cbpi_config_fixture import CraftBeerPiTestCase


class EventsTestCase(CraftBeerPiTestCase):

    async def poll(self, **params):
        resp = await self.client.get(path="/events", params=params)
        assert resp.status == 200
        assert resp.headers["Cache-Control"] == "no-store"
        return await resp.json()

    async def test_first_poll_gives_position_and_snapshot(self):
        self.cbpi.ws.send(dict(topic="sensorstate", id="s1", value=20))
        self.cbpi.ws.send(dict(topic="notifiaction", id="n1", title="old popup"))
        m = await self.poll()
        assert m["reset"] is True
        assert dict(topic="sensorstate", id="s1", value=20) in m["events"]
        assert all(e["topic"] != "notifiaction" for e in m["events"])
        assert m["epoch"] == self.cbpi.ws.events.epoch
        assert m["seq"] == self.cbpi.ws.events.seq

    async def test_wrong_epoch_resets(self):
        m = await self.poll()
        m2 = await self.poll(epoch="old", since=m["seq"], timeout=0)
        assert m2["reset"] is True

    async def test_poll_returns_new_events(self):
        m = await self.poll()
        self.cbpi.ws.send(dict(topic="actorupdate", data=[{"name": "b"}, {"name": "a"}]), True)
        m2 = await self.poll(epoch=m["epoch"], since=m["seq"], timeout=0)
        assert m2["reset"] is False
        assert m2["events"] == [dict(topic="actorupdate", data=[{"name": "a"}, {"name": "b"}])]
        assert m2["seq"] == m["seq"] + 1

    async def test_long_poll_wakes_up_on_event(self):
        m = await self.poll()

        async def later():
            await asyncio.sleep(0.3)
            self.cbpi.ws.send(dict(topic="sensorstate", id="s1", value=21.5))

        asyncio.create_task(later())
        start = time.monotonic()
        m2 = await self.poll(epoch=m["epoch"], since=m["seq"], timeout=10)
        assert time.monotonic() - start < 5
        assert m2["events"][-1]["value"] == 21.5

    async def test_long_poll_times_out_empty(self):
        m = await self.poll()
        start = time.monotonic()
        m2 = await self.poll(epoch=m["epoch"], since=m["seq"], timeout=0.5)
        assert time.monotonic() - start >= 0.5
        assert m2["reset"] is False
        assert m2["events"] == []

    async def test_bus_events_not_in_log(self):
        before = self.cbpi.ws.events.seq
        await self.cbpi.ws.listen("job/some/done", a=1)
        assert self.cbpi.ws.events.seq == before


class EventLogTestCase(CraftBeerPiTestCase):

    async def test_coalescing(self):
        log = EventLog()
        log.append(dict(topic="sensorstate", id="s1", value=1))
        log.append(dict(topic="sensorstate", id="s2", value=5))
        log.append(dict(topic="sensorstate", id="s1", value=2))
        log.append(dict(topic="notifiaction", id="n1", title="x"))
        log.append(dict(topic="notifiaction", id="n2", title="y"))
        reset, events = log.since(0)
        assert reset is False
        assert events == [
            '{"topic": "sensorstate", "id": "s2", "value": 5}',
            '{"topic": "sensorstate", "id": "s1", "value": 2}',
            '{"topic": "notifiaction", "id": "n1", "title": "x"}',
            '{"topic": "notifiaction", "id": "n2", "title": "y"}',
        ]
        # only what came after seq 3
        reset, events = log.since(3)
        assert len(events) == 2

    async def test_snapshot_at_send_time(self):
        log = EventLog()
        live = [1]
        log.append(dict(topic="notificationupdate", data=live))
        live.append(2)
        assert log.since(0)[1] == ['{"topic": "notificationupdate", "data": [1]}']

    async def test_overflow_forces_reset(self):
        log = EventLog(max_size=3)
        for i in range(5):
            log.append(dict(topic="notifiaction", id=str(i)))
        reset, events = log.since(0)
        assert reset is True
        # notifications are not replayed
        assert events == []
        assert log.since(1)[0] is True
        reset, events = log.since(2)
        assert reset is False
        assert len(events) == 3

    async def test_unserializable_is_dropped(self):
        log = EventLog()
        circular = {}
        circular["self"] = circular
        log.append(dict(topic="x", data=circular))
        assert log.seq == 0
