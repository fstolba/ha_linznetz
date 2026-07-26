"""Sensor platform for linznetz."""

import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
import logging
import os
import voluptuous as vol
from aiohttp.web_request import FileField

from homeassistant.components import webhook
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMeanType, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    get_last_statistics,
    async_import_statistics,
    statistics_during_period,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .api import LinzNetzApiClient, LinzNetzAuthError, LinzNetzConnectionError
from .const import (
    CONF_METER_POINT_NUMBER,
    CONF_NAME,
    DEFAULT_NAME,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
    SERVICE_IMPORT_REPORT,
    END_TIME_KEY,
    START_TIME_KEY,
    CONF_WEBHOOK_ID,
ATTR_METER_POINT_NUMBER,
ATTR_WEBHOOK_URL,
ATTR_WEBHOOK_LAST_RECEIVED,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_devices
):
    """Setup sensor platform."""

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_IMPORT_REPORT,
        {
            vol.Optional("path"): str,
            vol.Optional("content"): set(),
        },
        LinzNetzSensor.import_report.__name__,
    )

    client = hass.data[DOMAIN][config_entry.entry_id].get("client")
    async_add_devices([LinzNetzSensor(config_entry, client)])


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the sensor platform."""
    github = GitHubAPI(session, "requester", oauth_token=config[CONF_ACCESS_TOKEN])
    sensors = [GitHubRepoSensor(github, repo) for repo in config[CONF_REPOS]]
    async_add_entities(sensors, update_before_add=True)


def get_csv_data_value_key(csv_data: list) -> str:
    """Gets the key to access the value property from a given csv_data list."""
    return list(csv_data[0].keys())[2]


def parse_csv_date_str(csv_date_str: str) -> datetime:
    """Parses the Austrian time string to an UTC datetime."""
    parsed_str = dt_util.as_utc(
        datetime.strptime(csv_date_str, "%d.%m.%Y %H:%M").replace(
            tzinfo=dt_util.get_time_zone("Europe/Vienna")
        )
    )
    return parsed_str


def parse_german_number_str_to_decimal(number_str: str) -> Decimal:
    """Parses a German number string from the CSV to a Decimal."""
    return Decimal(number_str.replace(",", "."))


def parse_value_to_decimal(value) -> Decimal:
    """Parses a value to a decimal with floating point error workaround."""
    return Decimal(str(value))


def parse_statistic_value_to_datetime(value) -> datetime:
    """Parses a statistic value to datetime with provided backwards compatibility."""
    # parsing "from timestamp" is required since 2023.3.0
    return value if isinstance(value, datetime) else dt_util.utc_from_timestamp(value)


def get_csv_data_list_from_file(file_path: str):
    """Returns content on file as csv list."""
    if not os.path.isfile(file_path):
        raise HomeAssistantError(f"Report file at path {file_path} not found.")
    with open(file_path, encoding="UTF-8") as file:
        _LOGGER.debug(file)
        report_dict_reader = csv.DictReader(file, delimiter=";")
        csv_data = list(report_dict_reader)
    return csv_data


def validate_hour_block(hour_block: list) -> bool:
    """Validates the QH values in an hour block to be in the right order."""
    if len(hour_block) != 4:
        return False
    first_prefix = None
    for index, record in enumerate(hour_block, start=0):
        prefix, suffix = record[START_TIME_KEY].split(":")
        if index == 0:
            first_prefix = prefix
        if prefix != first_prefix:
            return False
        if int(suffix) != (index * 15):
            return False
    return True


class LinzNetzSensor(SensorEntity):
    """linznetz Sensor class."""
    _attr_last_webhook_receive: datetime | None = None
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, config_entry: ConfigEntry, client: LinzNetzApiClient | None = None):
        """Initialize the sensor."""
        self.config_entry = config_entry
        self._client = client
        self._meter_point_number = config_entry.data[CONF_METER_POINT_NUMBER]
        self._attr_name = f"{_name} Energy"

        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_should_poll = False
        self._attr_icon = "mdi:transmission-tower-import"
        self._attr_available = True

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._meter_point_number)}, name=_name
        )
        self._attr_unique_id = f"{self._meter_point_number}_energy"

        self._unsub_timer: CALLBACK_TYPE | None = None
        self._last_fetch_date: datetime | None = None

        meter_partial = user_input[CONF_METER_POINT_NUMBER][-8:]
        self._webhook_id = f"linznetz{meter_partial}"



    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        self.hass.custom_attributes = {
            ATTR_METER_POINT_NUMBER: self._meter_point_number,
        }

        # Registering the Webhook receiver so we can access it's data without HA type casting
        webhook.async_register(
            self.hass,
            DOMAIN,
            f"Linznetz {self._meter_point_number} webhook receiver",
            self._webhook_id,
            self.handle_file_webhook
        )
        url = webhook.async_generate_url(self.hass, self._webhook_id)
        self.hass.custom_attributes[ATTR_WEBHOOK_URL] = url
        _LOGGER.info(f"Webhook endpoint available at {url}.")

    async def handle_file_webhook(self, hass, webhook_id, request):
        """Directly process the incoming multipart form-data."""
        data = await request.post()

        _LOGGER.debug(f"Webhook received, payload {data}")
        file_field = data.get("file")

        if not file_field:
            _LOGGER.error("No file found in webhook form-data.")
            return

        self.hass.custom_attributes[ATTR_WEBHOOK_LAST_RECEIVED] = dt_util.utcnow()
        self._attr_last_webhook_receive = dt_util.utcnow()
        await self.import_report(None, file_field.file)

    @property
    def last_webhook_receive(self):
        """Return the translation key to translate the entity's name and states."""
        return self._attr_last_webhook_receive

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None
        webhook.async_unregister(self.hass, self._webhook_id)
        await super().async_will_remove_from_hass()

    async def async_update(self) -> None:
        """Automatically fetch and import data from LinzNetz portal."""
        if not self._client:
            return

        try:
            # Fetch data for yesterday (LinzNetz provides data with 1-2 day delay)
            date_to = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0)
            date_from = date_to - timedelta(days=3)  # Fetch last 3 days to catch gaps

            _LOGGER.debug(
                "Auto-fetching consumption data from %s to %s",
                date_from.strftime("%d.%m.%Y"),
                date_to.strftime("%d.%m.%Y"),
            )

            csv_data = await self._client.get_consumption_data(
                self._meter_point_number, date_from, date_to
            )

            if not csv_data:
                _LOGGER.debug("No new consumption data available")
                return

            # Trim trailing incomplete hour block (e.g. partial current day)
            remainder = len(csv_data) % 4
            if remainder != 0:
                _LOGGER.debug(
                    "Trimming %d trailing rows from %d total (incomplete hour block)",
                    remainder,
                    len(csv_data),
                )
                csv_data = csv_data[:-remainder]

            if not csv_data:
                _LOGGER.debug("No complete hour blocks in fetched data")
                return

            await self._import_csv_data(csv_data)
            self._last_fetch_date = dt_util.utcnow()
            _LOGGER.info(
                "Successfully auto-imported %d QH records from LinzNetz",
                len(csv_data),
            )

        except (LinzNetzAuthError, LinzNetzConnectionError) as err:
            _LOGGER.warning("Failed to auto-fetch data from LinzNetz: %s", err)
        except Exception:
            _LOGGER.exception("Unexpected error during auto-fetch from LinzNetz")

    @property
    def device_state_attributes(self):
        return self.hass.custom_attributes

    @property
    def extra_state_attributes(self):
        return self.device_state_attributes

    async def import_report(self, path = None, content = None):
        """Service to import csv data from path."""
        _LOGGER.debug("Import Report executed with path: %s", path)
        _LOGGER.debug("Import Report executed with content: %s", content)
        _LOGGER.debug(f"Content is of type {type(content)}")

        _LOGGER.debug(
            "Entity: %s; Entity_ID: %s; Unique_ID: %s",
            self.name,
            self.entity_id,
            self.unique_id,
        )


        if path is None and content is not None:
            report_dict_reader = csv.DictReader(io.TextIOWrapper(content, encoding="utf-8"), delimiter=";")
            csv_data = list(report_dict_reader)

        elif content is None and path is not None:
            csv_data = get_csv_data_list_from_file(path)
        else:
            raise HomeAssistantError(
                "path and content are mutually exclusive. You must only use one of those."
            )
        if len(csv_data) % 4 != 0:
            raise HomeAssistantError(
                "Report to import seems to be corrupted. Please ensure that there are at least 4 QH values per hour."
            )

        await self._import_csv_data(csv_data)

    async def _import_csv_data(self, csv_data: list) -> None:
        """Shared logic to import CSV data into HA statistics."""
        # metadata for internal stats
        metadata = StatisticMetaData(
            unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            source="recorder",
            name=self.name,
            statistic_id=self.entity_id,
            has_mean=False,
            has_sum=True,
            mean_type=StatisticMeanType.NONE,
            unit_class="energy",
        )
        statistics = []

        last_inserted_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, self.entity_id, True, {"sum"}
        )
        inserted_stats = {self.entity_id: []}
        _LOGGER.debug("Last inserted stat:")
        _LOGGER.debug(last_inserted_stat)

        if len(last_inserted_stat) == 0 or len(last_inserted_stat[self.entity_id]) == 0:
            _sum = Decimal(0)
            _LOGGER.debug("No previous inserted stats, start sum with 0.")
        elif (
            len(last_inserted_stat) == 1
            and len(last_inserted_stat[self.entity_id]) == 1
            and parse_statistic_value_to_datetime(
                last_inserted_stat[self.entity_id][0]["start"]
            )
            < parse_csv_date_str(csv_data[0][START_TIME_KEY])
        ):
            _sum = parse_value_to_decimal(last_inserted_stat[self.entity_id][0]["sum"])
            _LOGGER.debug("Previous inserted stats found, start sum with %f.", _sum)
        else:
            inserted_stats = await get_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                parse_csv_date_str(csv_data[0][START_TIME_KEY]) - timedelta(hours=1),
                None,
                [self.entity_id],
                "hour",
                None,
                {"sum", "state"},
            )
            _LOGGER.debug("Inserted stats:")
            _LOGGER.debug(inserted_stats)
            _sum = (
                parse_value_to_decimal(inserted_stats[self.entity_id][0]["sum"])
                if len(inserted_stats) > 0
                and len(inserted_stats[self.entity_id]) > 0
                and parse_statistic_value_to_datetime(
                    inserted_stats[self.entity_id][0]["start"]
                )
                < parse_csv_date_str(csv_data[0][START_TIME_KEY])
                else Decimal(0)
            )
            _LOGGER.debug("Overlap detected, start sum with %f.", _sum)

        hourly_sum = Decimal(0)
        start = None
        csv_data_value_key = get_csv_data_value_key(csv_data)
        daylight_saving_change_needs_additional_hour = False
        for index, record in enumerate(csv_data, start=1):
            hourly_sum += parse_german_number_str_to_decimal(record[csv_data_value_key])
            if index % 4 == 1:
                if not validate_hour_block(csv_data[(index - 1) : (index - 1) + 4]):
                    raise HomeAssistantError(
                        "Invalid hour block detected. Start time of QH values must always be in the following order: xx:00, xx:15, xx:30, xx:45."
                    )
                start = parse_csv_date_str(record[START_TIME_KEY])
                if daylight_saving_change_needs_additional_hour:
                    # double check for daylight saving change, reset the flag anyway
                    if start == statistics[-1]["start"]:
                        start += timedelta(hours=1)
                    daylight_saving_change_needs_additional_hour = False
            if index % 4 == 0:
                # LINZ NETZ indicates a winter daylight saving change when the start_time of an hour block is equal to the end_time.
                # Therefore it is necessary to add an additional (UTC) hour to the next hour.
                if start == parse_csv_date_str(record[END_TIME_KEY]):
                    daylight_saving_change_needs_additional_hour = True
                _sum += hourly_sum
                statistics.append(
                    StatisticData(
                        start=start,
                        state=hourly_sum,
                        sum=_sum,
                    )
                )
                hourly_sum = Decimal(0)
        last_added_stat = statistics[-1]
        for stat in inserted_stats[self.entity_id]:
            if (
                parse_statistic_value_to_datetime(stat["start"])
                <= last_added_stat["start"]
            ):
                continue
            _sum += parse_value_to_decimal(stat["state"])
            statistics.append(
                StatisticData(
                    start=parse_statistic_value_to_datetime(stat["start"]),
                    state=stat["state"],
                    sum=_sum,
                )
            )
        _LOGGER.debug(statistics)
        _LOGGER.debug(metadata)
        async_import_statistics(self.hass, metadata, statistics)
