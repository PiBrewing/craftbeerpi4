import time
from unittest import mock

from tests.cbpi_config_fixture import CraftBeerPiTestCase


class AuthTestCase(CraftBeerPiTestCase):
    # tests/cbpi-test-config/config.yaml
    CREDENTIALS = {"username": "cbpi", "password": "123"}

    async def login(self, **credentials):
        return await self.client.post("/login", data=credentials or self.CREDENTIALS)

    async def test_login_then_logout(self):
        resp = await self.login()
        assert resp.status == 200
        resp = await self.client.get("/logout")
        assert resp.status == 200
        # the logout forgot the login
        resp = await self.client.get("/logout")
        assert resp.status == 403

    async def test_wrong_password(self):
        resp = await self.login(username="cbpi", password="wrong")
        assert resp.status == 403
        resp = await self.client.get("/logout")
        assert resp.status == 403

    async def test_protected_route_without_login(self):
        resp = await self.client.get("/logout")
        assert resp.status == 403

    async def test_login_expires_after_60_seconds(self):
        resp = await self.login()
        assert resp.status == 200
        later = time.time() + 60
        with mock.patch("cbpi.auth.time.time", return_value=later):
            resp = await self.client.get("/logout")
        assert resp.status == 403

    async def test_login_is_bound_to_the_client_address(self):
        resp = await self.login()
        assert resp.status == 200
        with mock.patch("cbpi.auth._client_ip", return_value="192.0.2.1"):
            resp = await self.client.get("/logout")
        assert resp.status == 403
