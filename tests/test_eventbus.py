import asyncio
import threading

from cbpi.eventbus import CBPiEventBus


def make_bus_outside_the_loop():
    # `cbpi start` builds CraftBeerPi, and with it the bus, before
    # web.run_app starts the loop that will run the application
    return CBPiEventBus(None, cbpi=None)


def test_fire_runs_handlers_on_the_running_loop():
    bus = make_bus_outside_the_loop()
    received = []

    async def handler(topic, **kwargs):
        received.append((topic, kwargs))

    bus.register("kettle/+/update", handler)

    async def main():
        await bus.fire("kettle/1/update", value=42)
        await asyncio.sleep(0.01)

    asyncio.run(main())
    assert received == [("kettle/1/update", {"value": 42})]


def test_fire_collects_handler_results():
    bus = make_bus_outside_the_loop()

    async def handler(topic, future, **kwargs):
        future.set_result("done")

    bus.register("job/done", handler)

    async def main():
        return await bus.fire("job/done", timeout=1)

    results = asyncio.run(main())
    assert results.timeout is False
    assert results.get("%s.handler" % __name__) == ("done", True)


def test_sync_fire_from_the_loop():
    bus = make_bus_outside_the_loop()
    received = []

    async def handler(topic, **kwargs):
        received.append(topic)

    bus.register("job/+/done", handler)

    async def main():
        bus.sync_fire("job/x/done")
        await asyncio.sleep(0.01)

    asyncio.run(main())
    assert received == ["job/x/done"]


def test_sync_fire_from_a_thread():
    bus = make_bus_outside_the_loop()
    received = []

    async def handler(topic, **kwargs):
        received.append(topic)

    async def main():
        # plugins register at startup, inside the loop
        bus.register("sensor/+/data", handler)
        thread = threading.Thread(target=bus.sync_fire, args=("sensor/1/data",))
        thread.start()
        await asyncio.get_running_loop().run_in_executor(None, thread.join)
        await asyncio.sleep(0.05)

    asyncio.run(main())
    assert received == ["sensor/1/data"]


def test_sync_fire_from_a_thread_before_the_loop_runs():
    bus = make_bus_outside_the_loop()

    async def handler(topic, **kwargs):
        pass

    bus.register("sensor/+/data", handler)
    errors = []

    def fire():
        try:
            bus.sync_fire("sensor/1/data")
        except Exception as e:
            errors.append(e)

    thread = threading.Thread(target=fire)
    thread.start()
    thread.join()
    # dropped with a warning, not raised into the plugin's thread
    assert errors == []
