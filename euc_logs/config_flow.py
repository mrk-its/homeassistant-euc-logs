"""Config flow for EUC Logs."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_entry_oauth2_flow
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class OAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Config flow to handle EUC Logs OAuth2 authentication."""

    DOMAIN = DOMAIN
    # TODO Pick one from config_entries.CONN_CLASS_*
    CONNECTION_CLASS = config_entries.CONN_CLASS_UNKNOWN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)

    async def async_step_extra(self, data: dict):
        if not data:
            return self.async_show_form(
                step_id="extra",
                data_schema=vol.Schema({
                    vol.Required("name"): str,
                    vol.Optional("last_file_processed", default=""): str,
                }),
                errors={},
            )
        data.update(self.oauth_data)
        return self.async_create_entry(title=self.flow_impl.name, data=data)

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an entry for the flow.

        Ok to override if you want to fetch extra info or even add another step.
        """
        self.oauth_data = data
        return await self.async_step_extra({})
