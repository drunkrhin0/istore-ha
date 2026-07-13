"""Unit tests for iStore API authentication helpers."""

import base64
from unittest.mock import MagicMock, AsyncMock
import pytest

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend

from custom_components.istore_heatpump.api import _encrypt_password, _VALID_CODES, IStoreApiError, IStoreAuthError
from custom_components.istore_heatpump import api as api_module


def generate_rsa_keypair(key_size=2048):
    """Generate an RSA key pair for testing _encrypt_password."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size, backend=default_backend()
    )
    public_key = private_key.public_key()
    public_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    public_key_b64 = base64.b64encode(public_der).decode("utf-8")
    return private_key, public_key_b64


class TestEncryptPassword:
    """Tests for _encrypt_password — the pure RSA-OAEP encryption function."""

    @pytest.fixture(autouse=True)
    def setup_keys(self):
        self.private_key, self.public_key_b64 = generate_rsa_keypair()

    def test_output_is_valid_base64(self):
        result = _encrypt_password(self.public_key_b64, "testpassword")
        decoded = base64.b64decode(result)
        assert isinstance(decoded, bytes)
        assert len(decoded) > 0

    def test_output_is_not_plaintext_password(self):
        password = "mySecret123!"
        result = _encrypt_password(self.public_key_b64, password)
        assert password not in result
        assert password.encode("utf-8") not in base64.b64decode(result)

    def test_roundtrip_decryption(self):
        password = "correct-horse-battery-staple"
        encrypted_b64 = _encrypt_password(self.public_key_b64, password)
        encrypted_bytes = base64.b64decode(encrypted_b64)
        decrypted = self.private_key.decrypt(
            encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        assert decrypted.decode("utf-8") == password

    def test_different_plaintexts_produce_different_ciphertexts(self):
        result_a = _encrypt_password(self.public_key_b64, "alpha")
        result_b = _encrypt_password(self.public_key_b64, "beta")
        assert result_a != result_b

    def test_same_plaintext_produces_different_ciphertexts(self):
        result_1 = _encrypt_password(self.public_key_b64, "same")
        result_2 = _encrypt_password(self.public_key_b64, "same")
        assert result_1 != result_2

    def test_empty_password(self):
        result = _encrypt_password(self.public_key_b64, "")
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_special_characters(self):
        password = "p@ssw0rd! 🚀 ñoño"
        encrypted_b64 = _encrypt_password(self.public_key_b64, password)
        encrypted_bytes = base64.b64decode(encrypted_b64)
        decrypted = self.private_key.decrypt(
            encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
        assert decrypted.decode("utf-8") == password

    def test_invalid_public_key_raises(self):
        with pytest.raises(Exception):
            _encrypt_password("not-a-real-key!!!", "password")


class TestGetAppId:
    """Tests for _get_app_id response parsing logic."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        resp = AsyncMock()
        session.get = MagicMock()
        cm = MagicMock()

        async def mock_aenter(self_arg=None):
            return resp
        async def mock_aexit(self_arg=None, *args):
            pass

        cm.__aenter__ = mock_aenter
        cm.__aexit__ = mock_aexit
        session.get.return_value = cm
        return session, resp

    def make_response(self, resp_mock, code=0, categories=None):
        body = {"code": code, "data": {"categories": categories or []}}
        resp_mock.json.return_value = body

    @pytest.mark.asyncio
    async def test_happy_path_finds_univers_ems(self, mock_session):
        session, resp = mock_session
        self.make_response(
            resp, code=200,
            categories=[
                {"name": "Other Category", "apps": [{"code": "SomeApp", "id": "app-1"}]},
                {"name": "Smart Grid", "apps": [
                    {"code": "OtherEMS", "id": "app-2"},
                    {"code": "Univers_EMS", "id": "app-univers-99"},
                ]},
            ],
        )
        result = await api_module._get_app_id(session, "fake-token")
        assert result == "app-univers-99"

    @pytest.mark.asyncio
    async def test_success_code_zero(self, mock_session):
        session, resp = mock_session
        self.make_response(resp, code=0, categories=[
            {"name": "Smart Grid", "apps": [{"code": "Univers_EMS", "id": "app-zero"}]}
        ])
        result = await api_module._get_app_id(session, "fake-token")
        assert result == "app-zero"

    @pytest.mark.asyncio
    async def test_missing_smart_grid_category_raises(self, mock_session):
        session, resp = mock_session
        self.make_response(resp, code=0, categories=[{"name": "Energy", "apps": []}])
        with pytest.raises(IStoreApiError, match="Could not find Univers_EMS"):
            await api_module._get_app_id(session, "fake-token")

    @pytest.mark.asyncio
    async def test_smart_grid_has_no_univers_ems_raises(self, mock_session):
        session, resp = mock_session
        self.make_response(resp, code=0, categories=[
            {"name": "Smart Grid", "apps": [{"code": "Battery_EMS", "id": "app-batt"}]}
        ])
        with pytest.raises(IStoreApiError, match="Could not find Univers_EMS"):
            await api_module._get_app_id(session, "fake-token")

    @pytest.mark.asyncio
    async def test_empty_categories_raises(self, mock_session):
        session, resp = mock_session
        self.make_response(resp, code=0, categories=[])
        with pytest.raises(IStoreApiError, match="Could not find Univers_EMS"):
            await api_module._get_app_id(session, "fake-token")

    @pytest.mark.asyncio
    async def test_error_code_raises(self, mock_session):
        session, resp = mock_session
        resp.json.return_value = {"code": 500, "message": "Server Error"}
        with pytest.raises(IStoreApiError, match="app resource list failed"):
            await api_module._get_app_id(session, "fake-token")


class TestGetSiteId:
    """Tests for _get_site_id response parsing logic."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        resp = AsyncMock()
        session.post = MagicMock()
        cm = MagicMock()

        async def mock_aenter(self_arg=None):
            return resp
        async def mock_aexit(self_arg=None, *args):
            pass

        cm.__aenter__ = mock_aenter
        cm.__aexit__ = mock_aexit
        session.post.return_value = cm
        return session, resp

    def make_response(self, resp_mock, code=0, children=None):
        body = {"code": code, "data": {"children": children or []}}
        resp_mock.json.return_value = body

    @pytest.mark.asyncio
    async def test_happy_path_finds_site_id(self, mock_session):
        session, resp = mock_session
        self.make_response(resp, code=200, children=[
            {"name": "Top Level", "children": [
                {"name": "Istore home owner", "children": [
                    {"name": "Device 1", "id": "site-abc-123"}
                ]}
            ]}
        ])
        result = await api_module._get_site_id(session, "token", "app-id")
        assert result == "site-abc-123"

    @pytest.mark.asyncio
    async def test_missing_istore_home_owner_raises(self, mock_session):
        session, resp = mock_session
        self.make_response(resp, code=0, children=[
            {"name": "Top", "children": [
                {"name": "Other Owner", "children": []}
            ]}
        ])
        with pytest.raises(IStoreApiError, match="Could not find site"):
            await api_module._get_site_id(session, "token", "app-id")

    @pytest.mark.asyncio
    async def test_empty_children_raises(self, mock_session):
        session, resp = mock_session
        self.make_response(resp, code=0, children=[])
        with pytest.raises(IStoreApiError, match="Could not find site"):
            await api_module._get_site_id(session, "token", "app-id")

    @pytest.mark.asyncio
    async def test_error_code_raises(self, mock_session):
        session, resp = mock_session
        resp.json.return_value = {"code": 403, "message": "Forbidden"}
        with pytest.raises(IStoreApiError, match="asset tree failed"):
            await api_module._get_site_id(session, "token", "app-id")


def test_valid_codes():
    """Verify the set of success codes recognized across endpoints."""
    assert 0 in _VALID_CODES
    assert 200 in _VALID_CODES
    assert 10000 in _VALID_CODES
    assert len(_VALID_CODES) == 3

