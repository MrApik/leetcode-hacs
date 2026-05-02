"""Common base classes for LeetCode entities."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import LeetCodeDataUpdateCoordinator


class _LeetCodeEntity(CoordinatorEntity[LeetCodeDataUpdateCoordinator]):
    """Shared base for both user-scoped and globally-scoped entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LeetCodeDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Wire up coordinator subscription and a per-username unique-id."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{coordinator.client.username}_{entity_description.key}"

    @property
    def available(self) -> bool:
        """Return whether the most recent coordinator refresh succeeded."""
        return super().available and self.coordinator.data is not None


class LeetCodeUserEntity(_LeetCodeEntity):
    """Entity attached to the per-user `LeetCode <username>` device."""

    def __init__(
        self,
        coordinator: LeetCodeDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Build the per-user device info on top of the shared init."""
        super().__init__(coordinator, entity_description)
        username = coordinator.client.username
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, username)},
            name=f"{MANUFACTURER} {username}",
            manufacturer=MANUFACTURER,
            model="LeetCode profile",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=f"https://leetcode.com/{username}/",
        )


class LeetCodeGlobalEntity(_LeetCodeEntity):
    """Entity attached to the shared `LeetCode` device.

    Holds data that is identical for every LeetCode user — today's daily
    challenge and the upcoming-contest schedule. The device identifier
    embeds the username so multiple config entries each register their own
    registry record (HA does not share devices across config entries by
    default).
    """

    def __init__(
        self,
        coordinator: LeetCodeDataUpdateCoordinator,
        entity_description: EntityDescription,
    ) -> None:
        """Build the global device info on top of the shared init."""
        super().__init__(coordinator, entity_description)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"global_{coordinator.client.username}")},
            name=MANUFACTURER,
            manufacturer=MANUFACTURER,
            model="LeetCode",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://leetcode.com/problemset/",
        )
