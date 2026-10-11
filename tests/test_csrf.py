from tests.cbpi_config_fixture import CraftBeerPiTestCase

ACTOR_ID = "3CUJte4bkxDMFCtLX8eqsX"


class CsrfTestCase(CraftBeerPiTestCase):

    def actor_state(self):
        return self.cbpi.actor.find_by_id(ACTOR_ID).instance.state

    async def switch_on(self, headers):
        return await self.client.post(path="/actor/%s/on" % ACTOR_ID, headers=headers)

    async def test_cross_site_post_rejected(self):
        resp = await self.switch_on({"Sec-Fetch-Site": "cross-site"})
        assert resp.status == 403
        assert self.actor_state() is not True, "handler must not run"

    async def test_same_site_post_rejected(self):
        resp = await self.switch_on({"Sec-Fetch-Site": "same-site"})
        assert resp.status == 403
        assert self.actor_state() is not True

    async def test_same_origin_post_allowed(self):
        resp = await self.switch_on({"Sec-Fetch-Site": "same-origin"})
        assert resp.status == 200
        assert self.actor_state() is True

    async def test_user_initiated_post_allowed(self):
        resp = await self.switch_on({"Sec-Fetch-Site": "none"})
        assert resp.status == 200

    async def test_origin_matching_host_allowed(self):
        resp = await self.switch_on({"Origin": "http://cbpi.local:8000", "Host": "cbpi.local:8000"})
        assert resp.status == 200
        assert self.actor_state() is True

    async def test_origin_matching_forwarded_host_allowed(self):
        headers = {"Origin": "https://brew.example.org", "Host": "cbpi:8000",
                   "X-Forwarded-Host": "brew.example.org, nginx"}
        resp = await self.switch_on(headers)
        assert resp.status == 200

    async def test_foreign_origin_rejected(self):
        resp = await self.switch_on({"Origin": "https://evil.example.com", "Host": "cbpi.local:8000"})
        assert resp.status == 403
        assert self.actor_state() is not True

    async def test_null_origin_rejected(self):
        resp = await self.switch_on({"Origin": "null"})
        assert resp.status == 403

    async def test_no_headers_allowed(self):
        resp = await self.switch_on({})
        assert resp.status == 200
        assert self.actor_state() is True

    async def test_cross_site_get_allowed(self):
        resp = await self.client.get(path="/actor/", headers={"Sec-Fetch-Site": "cross-site",
                                                              "Origin": "https://evil.example.com"})
        assert resp.status == 200
