import asyncio
import os
import types
import warnings

from cbpi.job.aiohttp import get_scheduler_from_app, get_scheduler_from_request
from tests.cbpi_config_fixture import CraftBeerPiTestCase


class AiohttpCompatTestCase(CraftBeerPiTestCase):

    async def get_application(self):
        with warnings.catch_warnings(record=True) as self.caught:
            warnings.simplefilter("always")
            return await super().get_application()

    async def test_no_deprecation_warning_at_startup(self):
        deprecations = [str(w.message) for w in self.caught
                        if issubclass(w.category, DeprecationWarning)]
        assert deprecations == []

    async def test_middlewares_are_new_style(self):
        # old-style middleware factories are deprecated by aiohttp (#2252)
        for middleware in self.app.middlewares:
            assert getattr(middleware, "__middleware_version__", None) == 1, middleware

    async def test_scheduler_found_from_app_and_request(self):
        scheduler = get_scheduler_from_app(self.app)
        assert scheduler is not None
        request = types.SimpleNamespace(config_dict=self.app)
        assert get_scheduler_from_request(request) is scheduler

    async def test_clear_log_closes_the_log_file(self):
        name = "unconfigured_test_sensor_ID"
        os.makedirs(self.cbpi.log.logsFolderPath, exist_ok=True)
        self.cbpi.log.log_data(name, 1)
        # let the listener tasks open the log file
        for _ in range(3):
            await asyncio.sleep(0)
        handler = self.cbpi.log.datalogger[name].handlers[0]
        self.cbpi.log.clear_log(name)
        assert handler.stream is None
