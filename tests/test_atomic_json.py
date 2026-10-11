import glob
import json
import os
import shutil
import tempfile
import unittest

from cbpi.configFolder import ConfigFolder
from cbpi.utils.utils import write_json_atomic
from tests.cbpi_config_fixture import CraftBeerPiTestCase


class WriteJsonAtomicTestCase(unittest.TestCase):

    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = os.path.join(self.directory, "actor.json")

    def test_same_format_as_json_dump(self):
        data = dict(data=[dict(name="b", id="2"), dict(name="a", id="1")])
        write_json_atomic(self.path, data)
        with open(self.path) as file:
            content = file.read()
        assert content == json.dumps(data, indent=4, sort_keys=True)
        assert os.listdir(self.directory) == ["actor.json"]

    def test_failed_dump_keeps_old_content(self):
        write_json_atomic(self.path, dict(data=[dict(name="old")]))
        with open(self.path, "rb") as file:
            old = file.read()

        # the dump fails midway: the first item is already written
        with self.assertRaises(TypeError):
            write_json_atomic(self.path, dict(data=[dict(name="new"), object()]))

        with open(self.path, "rb") as file:
            assert file.read() == old
        assert os.listdir(self.directory) == ["actor.json"], "no temp file left behind"


class CorruptConfigTestCase(CraftBeerPiTestCase):
    """
    Runs cbpi on a temp copy of the test config, with a truncated actor.json
    (as left by a power cut mid-write) and a step_data.json that is not JSON.
    """

    ACTOR_JSON = b'{\n    "data": [\n        {\n            "id": "3CUJte4bkx'
    STEP_JSON = b"\x00\x00\x00\x00"

    def configuration(self):
        test_directory = os.path.dirname(__file__)
        self.temp_directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_directory)
        config_directory = os.path.join(self.temp_directory, "config")
        shutil.copytree(os.path.join(test_directory, "cbpi-test-config"), config_directory)
        with open(os.path.join(config_directory, "actor.json"), "wb") as file:
            file.write(self.ACTOR_JSON)
        with open(os.path.join(config_directory, "step_data.json"), "wb") as file:
            file.write(self.STEP_JSON)
        self.config_directory = config_directory
        return ConfigFolder(config_directory, os.path.join(self.temp_directory, "logs"))

    def assert_set_aside(self, name, content):
        corrupt = glob.glob(os.path.join(self.config_directory, name + ".corrupt-*"))
        assert len(corrupt) == 1, "corrupt file should be kept aside"
        with open(corrupt[0], "rb") as file:
            assert file.read() == content, "corrupt file should keep the original bytes"
        assert os.path.exists(os.path.join(self.config_directory, name))

    async def test_corrupt_files_are_set_aside(self):
        assert self.cbpi.actor.data == []
        self.assert_set_aside("actor.json", self.ACTOR_JSON)

        assert self.cbpi.step.profile == []
        self.assert_set_aside("step_data.json", self.STEP_JSON)

        # the user is told which file was set aside
        notifications = " ".join(str(n) for n in self.cbpi.notification.notifications)
        assert "actor.json.corrupt-" in notifications
        assert "step_data.json.corrupt-" in notifications

        # cbpi is up and the untouched files are still loaded
        resp = await self.client.request("GET", "/actor/")
        assert resp.status == 200
        assert len(self.cbpi.sensor.data) > 0


class NamelessItemTestCase(CraftBeerPiTestCase):
    """An item without a name used to make the loader wipe the whole file."""

    def configuration(self):
        test_directory = os.path.dirname(__file__)
        self.temp_directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_directory)
        config_directory = os.path.join(self.temp_directory, "config")
        shutil.copytree(os.path.join(test_directory, "cbpi-test-config"), config_directory)
        path = os.path.join(config_directory, "actor.json")
        with open(path) as file:
            data = json.load(file)
        data["data"].append(dict(id="nameless", props={}, type="DummyActor"))
        with open(path, "w") as file:
            json.dump(data, file, indent=4, sort_keys=True)
        self.config_directory = config_directory
        return ConfigFolder(config_directory, os.path.join(self.temp_directory, "logs"))

    async def test_nameless_item_loads(self):
        ids = [item.id for item in self.cbpi.actor.data]
        assert "nameless" in ids
        assert "3CUJte4bkxDMFCtLX8eqsX" in ids
        assert glob.glob(os.path.join(self.config_directory, "actor.json.corrupt-*")) == []
