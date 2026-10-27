# Writing plugins that fail safe

CraftBeerPi switches heaters, coolers and pumps. A plugin that keeps regulating
on a wrong reading, or that dies without anyone noticing, can leave a heater on
with nothing watching it. The server protects the core logics and sensors. This
page explains what it does for your plugin, and what your plugin can do to be
protected the same way.

Nothing here is required: existing plugins keep working unchanged.

## What the server does for every plugin

**An exception that leaves `run()` is no longer silent.** In a kettle logic, a
fermenter logic, a sensor or an actor, the base class logs it with a traceback,
sends an ERROR notification and marks the logic or device as stopped, so the
GUI no longer shows it as active. Then:

| Plugin type     | What happens on top of that                                                     |
| --------------- | ------------------------------------------------------------------------------- |
| Kettle logic    | the kettle's heater and agitator are switched off                               |
| Fermenter logic | the fermenter's heater, cooler and valve are switched off                       |
| Sensor          | its value is no longer usable for control (see below)                           |
| Actor           | the actor is switched off with `off()`                                          |
| Step            | a step whose `run()` raises sends a notification                                |

If your plugin catches its own exceptions and goes on, nothing changes for it.

**`Timer.stop()` no longer calls `on_done`.** A timer only calls its callback
when it actually runs out. Before, pausing a step stopped its timer and ran
`on_timer_done`, which usually moved on to the next step or sent "Step
finished". If you added a `stopped` flag to work around this, you can keep it;
it is now redundant.

**Editing an active step** stops the running instance and restarts the step
with the new settings. Before, the old instance kept running unseen next to the
new one.

**Actors are switched off** when they are edited or deleted, and at shutdown
only after the logics and steps have stopped, so these cannot switch them back
on.

## Kettle and fermenter logics: read the sensor with `get_control_value()`

`get_sensor_value(id).get("value")` returns whatever the sensor shows: `nan`
from an ESP whose probe is unplugged, the last value of an MQTT sensor that
stopped publishing an hour ago, or a placeholder such as `0` or `999` before the
first reading. Every comparison with NaN is false, so a hysteresis neither
switches on nor off, and a PID gets a NaN output that is neither `> 0` nor
`<= 0`: whatever was on stays on.

Read the sensor that drives your actors with `get_control_value()` instead:

```python
value = await self.get_control_value(self.kettle.sensor, [self.heater], self.kettle.name)
if value is None:
    await asyncio.sleep(1)
    continue
```

- **Arguments**: the sensor id, the actors to switch off while there is no usable
  reading (`None` entries are skipped), and a name used as the notification title.
- **Return value**: the reading as a `float`, or `None` when it is NaN, missing,
  older than the sensor's `stale_after`, or comes from a sensor whose loop died.
  In that case the actors have already been switched off.
- **Notifications**: one ERROR when the reading is lost and one INFO when it
  comes back, not one per loop. This is tracked per sensor, so a logic that reads
  two sensors (mash tun and RIMS, beer and chamber) can call it for each.

To get the same check without switching anything off, use
`self.get_sensor_usable_value(id)`. It returns the float or `None`.

A fermenter logic does the same with its fermenter's sensor and both actors:

```python
value = await self.get_control_value(
    self.fermenter.sensor, [self.heater, self.cooler], self.fermenter.name
)
```

Let unexpected errors leave `run()` instead of catching everything and looping:
the base class then switches your actors off and tells the user. If you clean
up in a `finally`, switch your actors off there too.

The built-in `Hysteresis` and `FermenterHysteresis` logics are examples.

## Sensors: say when a reading expires

A sensor only knows that a reading is fresh if it pushes it with
`push_update()`. Every finite value pushed records the time in
`self.value_time`. Set `self.stale_after` to say how long a reading stays
usable for control:

| `stale_after`  | Meaning                                                                  |
| -------------- | ------------------------------------------------------------------------ |
| `None`         | (default) no expiry, and a value is usable before the first reading      |
| seconds        | no usable value before the first reading, nor once it is that old       |
| `math.inf`     | no usable value before the first reading, then it never expires          |

Set it in `start()` or `__init__()`, from a property when your sensor has one:

```python
import math

async def start(self):
    await super().start()
    self.timeout = int(self.props.get("Timeout", 60))
    self.stale_after = self.timeout if self.timeout > 0 else math.inf
```

The core sensors use: MQTT and HTTP sensors their `Timeout` property
(`math.inf` when it is 0), 1-wire `2 × interval + 30` seconds.

A few rules go with it:

- **Don't push placeholders as readings.** `0` or `999` until the first value is
  finite, so it counts as a reading. Wait for real data before calling
  `push_update()`.
- **Don't push a value you could not read.** If the hardware returns an error or
  a NaN, skip `push_update()` (or set `self.value_time = None`) instead of
  pushing the last good value again.
- **Re-pushing a cached value refreshes it.** If your `run()` pushes the same
  cached value every second to keep the GUI up to date (for example with
  `push_update(self.value, False)`), set `self.value_time` right after to the
  time of the actual reading, taken with `time.monotonic()`. The 1-wire sensor
  does this: its reading thread stores `time.monotonic()` on each successful
  read, and `run()` copies it into `self.value_time` after `push_update()`.
- **Let fatal errors leave `run()`.** The sensor is then marked as failed, its
  value is no longer used for control and the user gets a notification.

## Actors

Nothing to do. If your actor runs a loop in `run()` (a PWM duty cycle, for
example) and it raises, the base class calls `off()` and notifies.
