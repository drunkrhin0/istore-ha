from datetime import timedelta
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import MAX_STALE_POLLS

_LOGGER = logging.getLogger(__name__)


class iStoreCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, api):
        self.api = api
        self._failed_polls = 0
        super().__init__(
            hass,
            _LOGGER,
            name="iStore Heat Pump",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self):
        """Fetch latest data from iStore API.

        A failed poll keeps the previous data for up to MAX_STALE_POLLS polls in
        a row, so a short cloud outage does not make every entity unavailable.
        """
        try:
            data = await self.api.get_measurements()
            result = data["data"]
        except Exception as e:
            self._failed_polls += 1
            if self.data is not None and self._failed_polls <= MAX_STALE_POLLS:
                _LOGGER.warning(
                    "iStore update failed (%s of %s allowed), keeping last data: %s",
                    self._failed_polls,
                    MAX_STALE_POLLS,
                    e,
                )
                return self.data
            _LOGGER.error("iStore update failed: %s", e)
            raise UpdateFailed(f"iStore update failed: {e}") from e

        self._failed_polls = 0
        return result
