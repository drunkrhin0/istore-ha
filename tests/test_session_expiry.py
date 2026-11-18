"""Tests for expired-session handling, stale-data tolerance and login at setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.istore_heatpump import api as api_module
from custom_components.istore_heatpump.api import IStoreApiError, iStoreApi
from custom_components.istore_heatpump.const import MAX_STALE_POLLS
from custom_components.istore_heatpump.coordinator import iStoreCoordinator

EXPIRED = {"code": 30000, "msg": "please sign in", "detail": "Please login first."}
GOOD = {"code": 0, "data": {"dev": {"points": {}}}}


class FakeResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def json(self, content_type=None):
        if self._body is ValueError:
            raise ValueError("not json")
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Returns scripted (status, body) pairs and records the bearer token used."""

    def __init__(self, script):
        self.script = list(script)
        self.tokens = []

    def post(self, url, headers=None, **kwargs):
        self.tokens.append(headers["Authorization"])
        status, body = self.script.pop(0)
        return FakeResponse(status, body)


def make_api(script):
    api = iStoreApi("user", "pw", "old-token", "site", "dev", MagicMock())
    api._session = FakeSession(script)
    api._get_session = AsyncMock(return_value=api._session)
    return api


@pytest.fixture
def fake_login():
    with patch.object(
        api_module,
        "authenticate",
        AsyncMock(return_value={"access_token": "new-token", "parent_id": "site", "mdm_id": "dev"}),
    ) as login:
        yield login


class TestExpiredSession:
    @pytest.mark.asyncio
    async def test_body_code_30000_triggers_relogin_and_retry(self, fake_login):
        api = make_api([(200, EXPIRED), (200, GOOD)])
        assert await api.get_measurements() == GOOD
        fake_login.assert_awaited_once()
        assert api._session.tokens == ["Bearer old-token", "Bearer new-token"]

    @pytest.mark.asyncio
    async def test_http_401_with_non_json_body_triggers_relogin(self, fake_login):
        api = make_api([(401, ValueError), (200, GOOD)])
        assert await api.get_measurements() == GOOD
        fake_login.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_still_expired_after_relogin_raises_and_does_not_loop(self, fake_login):
        api = make_api([(200, EXPIRED), (200, EXPIRED)])
        with pytest.raises(IStoreApiError):
            await api.get_measurements()
        fake_login.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_good_response_does_not_login(self, fake_login):
        api = make_api([(200, GOOD)])
        await api.get_measurements()
        fake_login.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_token_already_refreshed_by_another_request_skips_login(self, fake_login):
        api = make_api([(200, EXPIRED), (200, GOOD)])
        original = api._session.post

        def post(url, headers=None, **kwargs):
            resp = original(url, headers=headers, **kwargs)
            api.access_token = "refreshed-elsewhere"
            return resp

        api._session.post = post
        await api.get_measurements()
        fake_login.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_control_call_recovers_from_expired_session(self, fake_login):
        api = make_api([(200, EXPIRED), (200, {"code": 0})])
        assert await api.set_onoff("Power", 1) == {"code": 0}
        fake_login.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timer_batch_recovers_from_expired_session(self, fake_login):
        api = make_api([(200, EXPIRED), (200, {"code": 10000})])
        assert await api.set_timers_batch({"PRI_RE_WH.Timer1On": 1}) == {"code": 10000}

    @pytest.mark.asyncio
    async def test_asset_name_recovers_from_expired_session(self, fake_login):
        api = make_api([(200, EXPIRED), (200, {"code": 0})])
        assert await api.update_asset_name("Tank") is True

    @pytest.mark.asyncio
    async def test_control_failure_code_still_raises(self, fake_login):
        api = make_api([(200, {"code": 500, "msg": "nope"})])
        with pytest.raises(IStoreApiError):
            await api.set_onoff("Power", 1)

    @pytest.mark.asyncio
    async def test_measurements_without_data_key_raises(self, fake_login):
        api = make_api([(200, {"code": 500})])
        with pytest.raises(IStoreApiError, match="no data"):
            await api.get_measurements()

    @pytest.mark.asyncio
    async def test_measurements_http_error_raises(self, fake_login):
        api = make_api([(503, {})])
        with pytest.raises(IStoreApiError, match="503"):
            await api.get_measurements()


class TestStaleDataTolerance:
    def make(self, results):
        api = MagicMock()
        api.get_measurements = AsyncMock(side_effect=results)
        return iStoreCoordinator(MagicMock(), api)

    @pytest.mark.asyncio
    async def test_first_poll_failure_raises(self):
        coord = self.make([IStoreApiError("boom")])
        with pytest.raises(Exception, match="boom"):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_failures_keep_last_data_up_to_limit_then_raise(self):
        good = {"data": {"dev": {"points": {"x": 1}}}}
        coord = self.make([good] + [IStoreApiError("down")] * (MAX_STALE_POLLS + 1))
        coord.data = await coord._async_update_data()
        for _ in range(MAX_STALE_POLLS):
            assert await coord._async_update_data() == coord.data
        with pytest.raises(Exception, match="down"):
            await coord._async_update_data()

    @pytest.mark.asyncio
    async def test_success_resets_the_failure_count(self):
        good = {"data": {"dev": {}}}
        coord = self.make(
            [good] + [IStoreApiError("down")] * MAX_STALE_POLLS + [good]
            + [IStoreApiError("down")] * MAX_STALE_POLLS
        )
        coord.data = await coord._async_update_data()
        for _ in range(MAX_STALE_POLLS):
            await coord._async_update_data()
        coord.data = await coord._async_update_data()
        for _ in range(MAX_STALE_POLLS):
            assert await coord._async_update_data() == coord.data

    @pytest.mark.asyncio
    async def test_response_without_data_key_counts_as_failure(self):
        coord = self.make([{"code": 30000}])
        with pytest.raises(Exception):
            await coord._async_update_data()


class TestSetupLogin:
    def entry(self):
        entry = MagicMock()
        entry.data = {
            "username": "u", "password": "p", "access_token": "t",
            "parent_id": "s", "mdm_id": "d",
        }
        return entry

    async def run_setup(self, relogin, order=None):
        from custom_components.istore_heatpump import async_setup_entry

        api = MagicMock()
        api.re_authenticate = relogin
        api.get_architecture = AsyncMock(return_value=None)
        api.get_attributes = AsyncMock(return_value=None)
        coordinator = MagicMock()

        async def first_refresh():
            if order is not None:
                order.append("refresh")

        coordinator.async_config_entry_first_refresh = first_refresh
        hass = MagicMock()
        hass.data = {}
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        with patch("custom_components.istore_heatpump.iStoreApi", return_value=api), \
             patch("custom_components.istore_heatpump.iStoreCoordinator", return_value=coordinator):
            return await async_setup_entry(hass, self.entry())

    @pytest.mark.asyncio
    async def test_setup_logs_in_before_first_refresh(self):
        order = []

        async def relogin():
            order.append("login")

        assert await self.run_setup(relogin, order) is True
        assert order == ["login", "refresh"]

    @pytest.mark.asyncio
    async def test_setup_falls_back_to_saved_token_when_login_fails(self):
        order = []
        relogin = AsyncMock(side_effect=IStoreApiError("cloud down"))
        assert await self.run_setup(relogin, order) is True
        assert order == ["refresh"]
