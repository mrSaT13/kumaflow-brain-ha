"""Сенсоры KumaFlow Brain.

Основное — прогресс сканирования библиотеки и sonic-анализа, как и было
в постановке задачи. Плюс несколько дешёвых, которые обычно нужны рядом.

Все фазы и статусы сверены с server/app/db/models.py:430-441 (ScanRun)
и server/app/api/scan.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, active_run, latest_run, progress_pct
from .const import (
    CONF_USER_ID,
    PHASE_ANALYSIS,
    PHASE_CLAP,
    PHASE_CLUSTERS,
    PHASE_LIBRARY,
    PHASE_LYRICS,
)


def _attr_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


class BrainSensorBase(CoordinatorEntity):
    """Общая часть: доступ к данным координатора."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        label: str = "",
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        # Короткий латинский id для YAML и автоматизаций: без него из-за
        # кириллических имён HA собрал бы entity_id вроде
        # sensor.skanirovanie_biblioteki_progress. В карточках это
        # нечитаемо, и переименовывать пришлось бы везде вручную.
        self._attr_suggested_object_id = f"kf_{key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"KumaFlow Brain {self._entry.title}",
            "manufacturer": "KumaFlow",
            "model": "Brain",
            "sw_version": (self.coordinator.data or {}).get("health", {}).get("version"),
        }

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data)


class BrainRunProgress(BrainSensorBase, SensorEntity):
    """Прогресс активного прогона: процент и «идёт / не идёт»."""

    # DeviceClass для процента в HA НЕ существует: SensorDeviceClass —
    # это enum, и члена PROGRESS в нём нет. Задание выдуманного имени
    # роняет импорт всего модуля sensor.py, а с ним и все сенсоры.
    # Поэтому просто единица измерения без device_class, как и делают
    # встроенные интеграции для процентов выполнения.
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:progress-upload"

    def __init__(self, coordinator, entry, key, name, phase) -> None:
        super().__init__(coordinator, entry, key, name)
        self._phase = phase

    @property
    def _run(self) -> dict | None:
        return active_run(self._runs, self._phase) or latest_run(self._runs, self._phase)

    @property
    def native_value(self) -> float | None:
        run = self._run
        return progress_pct(run) if run else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        run = self._run
        if not run:
            return {}
        return {
            "phase": run.get("phase"),
            "status": run.get("status"),
            "running": run.get("status") in ("queued", "running"),
            "processed_items": run.get("processed_items"),
            "total_items": run.get("total_items"),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "error": run.get("error"),
        }


class BrainRunStatus(BrainSensorBase, SensorEntity):
    """Строковый статус последнего прогона фазы."""

    _attr_icon = "mdi:state-machine"

    def __init__(self, coordinator, entry, key, name, phase) -> None:
        super().__init__(coordinator, entry, key, name)
        self._phase = phase

    @property
    def native_value(self) -> str | None:
        run = active_run(self._runs, self._phase) or latest_run(self._runs, self._phase)
        return run.get("status") if run else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        run = active_run(self._runs, self._phase) or latest_run(self._runs, self._phase)
        if not run:
            return {}
        return {
            "run_id": run.get("id"),
            "processed_items": run.get("processed_items"),
            "total_items": run.get("total_items"),
            "error": run.get("error"),
        }


class BrainRunFinished(BrainSensorBase, SensorEntity):
    """Время окончания последнего прогона фазы."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check"

    def __init__(self, coordinator, entry, key, name, phase) -> None:
        super().__init__(coordinator, entry, key, name)
        self._phase = phase

    @property
    def native_value(self) -> datetime | None:
        run = latest_run(self._runs, self._phase)
        return _attr_ts(run.get("finished_at")) if run else None


class BrainLibraryCount(BrainSensorBase, SensorEntity):
    """Всего треков в библиотеке."""

    _attr_icon = "mdi:music-note-multiple"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        health = (self.coordinator.data or {}).get("health") or {}
        for key in ("tracks", "total_tracks", "track_count"):
            if isinstance(health.get(key), int):
                return health[key]
        return None


class BrainHealthSensor(BrainSensorBase, SensorEntity):
    """Доступность мозга: 1 — отвечает, 0 — нет."""

    _attr_icon = "mdi:heart-pulse"

    @property
    def native_value(self) -> int:
        return 1 if self.coordinator.data else 0


# Полные ключи объявлены строками, а не собираются из фазы. Иначе их
# невозможно сверить с icons/icon.json — а именно эту сверку делает
# check.py, раздел 5. Три ключа на фазу: прогресс, статус, завершён.
#
#   (ключ_прогресса, ключ_статуса, ключ_завершения, подпись, фаза)
RUN_SENSOR_SETS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "library_progress",
        "library_status",
        "library_finished",
        "Сканирование библиотеки",
        PHASE_LIBRARY,
    ),
    (
        "analysis_progress",
        "analysis_status",
        "analysis_finished",
        "Sonic-анализ",
        PHASE_ANALYSIS,
    ),
    (
        "clap_progress",
        "clap_status",
        "clap_finished",
        "CLAP-эмбеддинги",
        PHASE_CLAP,
    ),
    (
        "lyrics_progress",
        "lyrics_status",
        "lyrics_finished",
        "Тексты треков",
        PHASE_LYRICS,
    ),
    (
        "clusters_progress",
        "clusters_status",
        "clusters_finished",
        "Кластеры",
        PHASE_CLUSTERS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities: list[SensorEntity] = [
        BrainHealthSensor(coordinator, entry, "health", "Доступность"),
        BrainLibraryCount(coordinator, entry, "tracks", "Треков в библиотеке"),
    ]

    for prog_key, stat_key, fin_key, label, phase in RUN_SENSOR_SETS:
        entities.append(
            BrainRunProgress(coordinator, entry, prog_key, f"{label}: прогресс", phase)
        )
        entities.append(
            BrainRunStatus(coordinator, entry, stat_key, f"{label}: статус", phase)
        )
        entities.append(
            BrainRunFinished(coordinator, entry, fin_key, f"{label}: завершён", phase)
        )

    async_add_entities(entities)
