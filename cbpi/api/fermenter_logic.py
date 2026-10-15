import asyncio
import logging
from abc import ABCMeta

from cbpi.api.base import CBPiBase
from cbpi.api.dataclasses import NotificationType
from cbpi.api.extension import CBPiExtension


class CBPiFermenterLogic(CBPiBase, metaclass=ABCMeta):

    def __init__(self, cbpi, id, props):
        self.cbpi = cbpi
        self.id = id
        self.props = props
        self.state = False
        self.running = False

    def init(self):
        pass

    async def on_start(self):
        pass

    async def on_stop(self):
        pass

    async def run(self):
        pass

    async def _run(self):

        try:
            await self.on_start()
            self.cancel_reason = await self.run()
        except asyncio.CancelledError as e:
            pass
        except Exception as e:
            await self._on_crash(e)
        finally:
            await self.on_stop()

    async def _on_crash(self, error):
        # A logic that dies used to vanish silently: the GUI kept showing it
        # active while nothing regulated any more, possibly with an actor on.
        self.state = False
        self.running = False
        item = self.cbpi.fermenter._find_by_id(self.id)
        name = item.name if item is not None else self.id
        logging.exception("Fermenter logic of {} stopped on an error".format(name))
        if item is not None:
            for actor in (item.heater, item.cooler, item.valve):
                if actor:
                    await self.actor_off(actor)
        self.cbpi.notify(
            "Fermenter logic stopped",
            "The logic of '{}' stopped on an error: {}. Its actors were switched off.".format(
                name, error
            ),
            NotificationType.ERROR,
        )
        try:
            self.cbpi.fermenter.push_update()
        except Exception:
            pass

    def get_state(self):
        return dict(running=self.state)

    async def start(self):

        self.state = True

    async def stop(self):

        self.task.cancel()
        await self.task
        self.state = False
