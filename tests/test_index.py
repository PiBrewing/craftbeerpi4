from aiohttp.test_utils import unittest_run_loop
from tests.cbpi_config_fixture import CraftBeerPiTestCase


class IndexTestCase(CraftBeerPiTestCase):

    async def test_index(self):


        # Test Index Page
        resp = await self.client.get(path="/")
        assert resp.status == 200

    async def test_html_not_cached(self):
        resp = await self.client.get(path="/static/test.html")
        assert resp.status == 200
        assert resp.content_type == "text/html"
        assert resp.headers["Cache-Control"] == "no-cache"

    async def test_static_assets_keep_cache_policy(self):
        resp = await self.client.get(path="/static/beer_icon.svg")
        assert resp.status == 200
        assert "Cache-Control" not in resp.headers

    async def test_404(self):
        # Test Index Page
        resp = await self.client.get(path="/abc")
        assert resp.status == 500

    async def test_wrong_login(self):
        resp = await self.client.post(path="/login", data={"username": "beer", "password": "123"})
        print("REPONSE STATUS", resp.status)
        assert resp.status == 403

    async def test_login(self):

        resp = await self.client.post(path="/login", data={"username": "cbpi", "password": "123"})
        print("REPONSE STATUS", resp.status)
        assert resp.status == 200

        resp = await self.client.get(path="/logout")
        print("REPONSE STATUS LGOUT", resp.status)
        assert resp.status == 200
