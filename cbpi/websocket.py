import asyncio
import logging
import weakref
from collections import defaultdict

import aiohttp
from aiohttp import web
from cbpi.eventlog import EventLog
from cbpi.utils import json_dumps
from voluptuous import Schema


class CBPiWebSocket:
    def __init__(self, cbpi) -> None:
        self.cbpi = cbpi
        self._callbacks = defaultdict(set)
        self._clients = weakref.WeakSet()
        self.logger = logging.getLogger(__name__)
        # GUI transport over plain HTTP (long-polling), alongside the websocket
        self.events = EventLog()
        self.cbpi.app.add_routes(
            [
                web.get("/ws", self.websocket_handler),
                web.get("/events", self.events.handler),
            ]
        )
        self.cbpi.app.on_shutdown.append(self.events.close)
        self.cbpi.bus.register_object(self)

        # if self.cbpi.config.static.get("ws_push_all", False):
        self.cbpi.bus.register("#", self.listen)

    async def listen(self, topic, **kwargs):
        data = dict(topic=topic, data=dict(**kwargs))
        self.logger.debug("PUSH %s " % data)
        # bus events stay websocket-only: the GUI uses none of them
        if self._clients:
            try:
                self._broadcast(data, json_dumps(data))
            except Exception as e:
                self.logger.error("Event not serializable, dropped: %s" % str(e))

    def send(self, data, sorting=False):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # called from a plugin thread: the event log and the clients belong to the loop
            self.cbpi.app.loop.call_soon_threadsafe(self.send, data, sorting)
            return
        if sorting:
            try:
                data["data"].sort(key=lambda x: x.get("name").upper())
            except:
                pass
        payload = self.events.append(data)
        if payload is not None:
            self._broadcast(data, payload)

    def _broadcast(self, data, payload):
        self.logger.debug("broadcast to ws clients. Data: %s" % data)
        for ws in self._clients:

            async def send_data(ws, payload):
                try:
                    await ws.send_str(payload)
                except Exception as e:
                    self.logger.error("Error with client %s: %s" % (ws, str(e)))

            self.cbpi.app.loop.create_task(send_data(ws, payload))

    async def websocket_handler(self, request):

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        try:
            peername = request.transport.get_extra_info("peername")
            if peername is not None:

                host = peername[0]
                port = peername[1]
            else:
                host, port = "Unknowen"
            self.logger.info(
                "Client Connected - Host: %s Port: %s  - client count: %s "
                % (host, port, len(self._clients))
            )
        except Exception as e:
            pass

        try:
            await ws.send_json(data=dict(topic="connection/success"))
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:

                    msg_obj = msg.json()
                    schema = Schema({"topic": str, "data": dict})
                    schema(msg_obj)

                    topic = msg_obj.get("topic")
                    data = msg_obj.get("data")
                    if topic == "close":
                        await ws.close()
                    else:
                        if data is not None:
                            await self.cbpi.bus.fire(topic=topic, **data)
                        else:
                            await self.cbpi.bus.fire(topic=topic)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.error(
                        "ws connection closed with exception %s" % ws.exception()
                    )

        except Exception as e:
            self.logger.error("%s - Received Data %s" % (str(e), msg.data))

        finally:
            self._clients.discard(ws)

        self.logger.info("Web Socket Close")

        return ws
