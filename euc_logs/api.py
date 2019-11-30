"""API for EUC Logs bound to HASS OAuth."""
from asyncio import run_coroutine_threadsafe
import datetime
import asyncio
import dateutil
import logging
import pytz
import time
import csv

from homeassistant import core, config_entries
from homeassistant.helpers import config_entry_oauth2_flow

# TODO the following two API examples are based on our suggested best practices
# for libraries using OAuth2 with requests or aiohttp. Delete the one you won't use.
# For more info see the docs at <insert url>.
_LOGGER = logging.getLogger(__name__)


class ConfigEntryAPI:
    """Provide test oauth authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        implementation: config_entry_oauth2_flow.AbstractOAuth2Implementation,
    ):
        """Initialize test oauth Auth."""
        self.hass = hass
        self.config_entry = config_entry
        self.session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )
        self.name = config_entry.data["name"]

    def refresh_tokens(self) -> dict:
        """Refresh and return new test oauth tokens using Home Assistant OAuth2 session."""
        run_coroutine_threadsafe(
            self.session.async_ensure_token_valid(), self.hass.loop
        ).result()
        return self.session.token

    UNITS = {
        "distance": "m",
        "total_distance": "m",
        "gps_speed": "km/h",
        "speed": "km/h",
        "voltage": "V",
        "current": "A",
        "power": "W",
        "battery_level": "%",
        "system_temp": "°C",
        "cpu_temp": "°C",
    }
    TRANSLATE = {"totaldistance": "total_distance"}
    SELECTED_METRICS = {
        "latitude",
        "longitude",
        "gps_speed",
        "speed",
        "voltage",
        "current",
        "power",
        "battery_level",
        "total_distance",
        "cpu_temp",
        "system_temp",
        "mode",
        "alert",
    }

    def create_events(self, prev_states, header, row):
        # datetime,latitude,longitude,gps_speed,gps_alt,gps_heading,gps_distance,speed,
        # voltage,current,power,battery_level,distance,totaldistance,system_temp,
        # cpu_temp,tilt,roll,mode,alert,wh,ah,wh_discharge,ah_discharge,wh_recharge,ah_recharge
        assert header[0] == "datetime"
        ts = dateutil.parser.parse(row[0]).astimezone(pytz.utc)

        for prop_name, prop_value in zip(header[1:], row[1:]):
            if prop_name not in self.SELECTED_METRICS:
                continue
            last_value, last_ts = prev_states.get(prop_name, (None, None))
            if last_value == prop_value and (ts - last_ts) < datetime.timedelta(seconds=300):
                continue
            prev_states[prop_name] = (prop_value, ts)
            attributes = {"source": "euc_logs"}
            unit = self.UNITS.get(prop_name)
            if unit:
                attributes["unit_of_measurement"] = unit
            entity_id = f"sensor.{self.name}_{prop_name}"
            state = core.State(entity_id, prop_value, attributes, ts, ts)
            event_data = {"entity_id": entity_id, "new_state": state}
            yield event_data

    def process_next_file(self, last_file_processed):
        import fs

        self.refresh_tokens()
        _LOGGER.info("looking for next file after: %s", last_file_processed)
        gfs = fs.open_fs(
            f"googledrive:///?access_token={self.session.token['access_token']}"
        )
        # gfs = fs.open_fs("file:///home/mrk/Documents")
        gfs = gfs.opendir("EucWorld Logs")
        files = sorted(list(gfs.scandir("")), key=lambda f: f.name)
        next_file = next(
            (
                f
                for f in files
                if f.name.endswith(".csv")
                and (not last_file_processed or f.name > last_file_processed)
            ),
            None,
        )
        if not next_file:
            return (None, 0)

        number_of_events = 0
        reader = csv.reader(gfs.open(next_file.name))
        header = next(reader)
        header = [self.TRANSLATE.get(name, name) for name in header]

        prev_states = {}
        for n, row in enumerate(reader):
            for event in self.create_events(prev_states, header, row):
                self.hass.bus.fire("state_changed", event)
                number_of_events += 1
                if not (number_of_events % 100):
                    time.sleep(0.2)
            _LOGGER.debug("file: %s, records: %s", next_file.name, number_of_events)

        return next_file.name, number_of_events

    async def async_run(self):
        last_file_processed = self.config_entry.data.get("last_file_processed")
        while True:
            (
                file_processed,
                number_of_records,
            ) = await self.hass.async_add_executor_job(
                self.process_next_file, last_file_processed
            )
            if file_processed:
                _LOGGER.info(
                    "processed file: %s, number of records: %s",
                    file_processed,
                    number_of_records,
                )
                if file_processed:
                    last_file_processed = file_processed
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={
                            **self.config_entry.data,
                            "last_file_processed": file_processed,
                        },
                    )
                    await asyncio.sleep(10)
                    continue
            await asyncio.sleep(60)
