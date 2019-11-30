"""The EUC Logs integration."""
import asyncio

import voluptuous as vol
from yarl import URL

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import (
    config_validation as cv,
    config_entry_oauth2_flow,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from . import config_flow
from . import api

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["sensor"]


class MyOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    async def async_generate_authorize_url(self, flow_id: str):
        """Generate a url for the user to authorize."""
        return str(
            URL(self.authorize_url).with_query(
                {
                    "response_type": "code",
                    "client_id": self.client_id,
                    "redirect_uri": self.redirect_uri,
                    "state": config_entry_oauth2_flow._encode_jwt(self.hass, {"flow_id": flow_id}),
                    "scope": "https://www.googleapis.com/auth/drive",
                    "prompt": "consent",
                    "access_type": "offline",
                }
            )
        )


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the EUC Logs component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        MyOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up EUC Logs from a config entry."""
    # Backwards compat
    if "auth_implementation" not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "auth_implementation": DOMAIN}
        )

    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    api_instance = api.ConfigEntryAPI(hass, entry, implementation)
    hass.data[DOMAIN]["API"] = api_instance

    hass.loop.create_task(api_instance.async_run())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
