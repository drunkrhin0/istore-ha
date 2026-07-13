import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_ACCESS_TOKEN, CONF_PARENT_ID, CONF_MDM_ID
from .api import authenticate, IStoreAuthError, IStoreApiError

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error raised when API connection fails."""


class InvalidAuth(HomeAssistantError):
    """Error for invalid authentication."""


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    @staticmethod
    def async_get_options_flow(config_entry):
        from .options_flow import OptionsFlowHandler
        return OptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            try:
                creds = await authenticate(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except IStoreAuthError:
                errors["base"] = "invalid_auth"
            except (IStoreApiError, aiohttp.ClientError, TimeoutError, OSError):
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during iStore setup")
                errors["base"] = "cannot_connect"

            if not errors:
                for existing_entry in self._async_current_entries():
                    if existing_entry.data.get(CONF_MDM_ID) == creds["mdm_id"]:
                        return self.async_abort(reason="already_configured")

                return self.async_create_entry(
                    title="iStore Heat Pump",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_ACCESS_TOKEN: creds["access_token"],
                        CONF_PARENT_ID: creds["parent_id"],
                        CONF_MDM_ID: creds["mdm_id"],
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
