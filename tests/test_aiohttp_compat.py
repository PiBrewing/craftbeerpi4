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

