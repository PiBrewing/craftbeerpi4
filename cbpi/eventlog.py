import asyncio
import logging
import time
from collections import OrderedDict

import shortuuid
from aiohttp import web
from cbpi.utils import json_dumps


# one-shot messages: not replayed to a client that (re)starts from scratch
ONE_SHOT_TOPICS = {"notifiaction"}


class EventLog:
    """
    Buffer of the messages pushed to the GUI, served over plain HTTP long-polling
    (GET /events) so the GUI does not need a websocket.

    Every message gets a sequence number. Messages that describe a state are
    coalesced: only the latest one per (topic, id) is kept, so a client that
    comes back after a while gets the current state and not the whole history.
    One-shot messages such as notifications carry a unique id and are therefore
    kept one by one, up to max_size.
    """

    def __init__(self, max_size=500):
        self.logger = logging.getLogger(__name__)
        # changes on every start: the client reloads its full state when it sees a new epoch
        self.epoch = shortuuid.uuid()
        self.seq = 0
        self.max_size = max_size
        # oldest sequence number still guaranteed to be in the buffer
        self.floor = 0
        self._events = OrderedDict()
        self._changed = asyncio.Event()

    @staticmethod
    def key(data):
        return (data.get("topic"), data.get("id"))

    def append(self, data):
        try:
            # serialize now: the payload is often a live list the controllers keep mutating
            payload = json_dumps(data)
        except Exception as e:
            self.logger.error("Event not serializable, dropped: %s" % str(e))
            return
        self.seq += 1
        key = self.key(data)
        self._events.pop(key, None)
        self._events[key] = (self.seq, payload)
        while len(self._events) > self.max_size:
            _, (seq, _) = self._events.popitem(last=False)
            self.floor = seq
        self._changed.set()
        self._changed = asyncio.Event()

    def snapshot(self):
        """Latest state messages, for a client that starts from scratch."""
        return [
            payload
            for (topic, _), (_, payload) in self._events.items()
            if topic not in ONE_SHOT_TOPICS
        ]

    def since(self, seq):
        """
        Return (reset, [payload, ...]) for the events newer than seq.
        On reset, the payloads are the current snapshot instead.
        """
        if seq < self.floor:
            return True, self.snapshot()
        events = []
        for s, payload in reversed(self._events.values()):
            if s <= seq:
                break
            events.append(payload)
        events.reverse()
        return False, events

    async def wait(self, seq, timeout):
        """Wait until an event newer than seq exists, or the timeout expires."""
        deadline = time.monotonic() + timeout
        while self.seq <= seq:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            try:
                await asyncio.wait_for(self._changed.wait(), remaining)
            except asyncio.TimeoutError:
                return

    def response(self, reset, events):
        body = '{"epoch":%s,"seq":%d,"reset":%s,"events":[%s]}' % (
            json_dumps(self.epoch),
            self.seq,
            "true" if reset else "false",
            ",".join(events),
        )
        return web.Response(
            body=body,
            content_type="application/json",
            headers={"Cache-Control": "no-store"},
        )

    async def handler(self, request):
        """
        GET /events?epoch=<epoch>&since=<seq>&timeout=<seconds>

        Answers at once when newer events exist, otherwise holds the request up to
        `timeout` seconds (max 55). reset=true means the client missed events
        (new epoch or buffer overflow): it must reload its full state, and the
        events of that answer are the latest state messages (sensor values...).
        """
        try:
            since = int(request.query.get("since", -1))
        except ValueError:
            since = -1
        try:
            timeout = min(max(float(request.query.get("timeout", 25)), 0), 55)
        except ValueError:
            timeout = 25
        epoch = request.query.get("epoch")

        if epoch != self.epoch or since < 0 or since > self.seq:
            # first poll, server restarted, or client ahead of us: give the position to start from
            return self.response(True, self.snapshot())

        await self.wait(since, timeout)
        if self.seq > since:
            # let a burst of updates (e.g. all sensors of one cycle) land in the same answer
            await asyncio.sleep(0.1)
        reset, events = self.since(since)
        return self.response(reset, events)
