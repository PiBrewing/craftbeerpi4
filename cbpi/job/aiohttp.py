from functools import wraps

from aiohttp.web import AppKey, View

from . import create_scheduler

__all__ = ("setup", "spawn", "get_scheduler", "get_scheduler_from_app", "atomic")

SCHEDULER_KEY = AppKey("AIOJOBS_SCHEDULER")


def get_scheduler(request):
    scheduler = get_scheduler_from_request(request)
    if scheduler is None:
        raise RuntimeError("Call aiojobs.aiohttp.setup() on application initialization")
    return scheduler


def get_scheduler_from_app(app):
    return app.get(SCHEDULER_KEY)


def get_scheduler_from_request(request):
    return request.config_dict.get(SCHEDULER_KEY)


async def spawn(request, coro, name="Manuel"):
    return await get_scheduler(request).spawn(coro)


def atomic(coro):
    @wraps(coro)
    async def wrapper(request):
        if isinstance(request, View):
            # Class Based View decorated.
            request = request.request

        job = await spawn(request, coro(request))
        return await job.wait()

    return wrapper


async def setup(app, cbpi, **kwargs):

    app[SCHEDULER_KEY] = await create_scheduler(cbpi, **kwargs)

    async def on_cleanup(app):
        await app[SCHEDULER_KEY].close()

    app.on_cleanup.append(on_cleanup)
