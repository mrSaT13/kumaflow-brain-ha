"""Интеграция KumaFlow Brain для Home Assistant.

Что даёт:
  * сенсоры прогресса сканирования библиотеки и sonic-анализа
  * кнопки ручного запуска дневного плейлиста и волны
  * кнопки запуска сканирования и анализа

Установка описана в README рядом, но коротко: скопировать папку
kumaflow_brain в config/custom_components/ и перезагрузить HA, либо
подключить репозиторий через HACS.
"""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BrainClient, BrainError
from .const import CONF_TOKEN, CONF_URL, CONF_USER_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOG = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_create_clientsession(hass)
    client = BrainClient(entry.data[CONF_URL], entry.data[CONF_TOKEN], session)

    coordinator = DataUpdateCoordinator(
        hass,
        _LOG,
        name=DOMAIN,
        update_interval=None,  # заполним после первого успешного опроса
        update_method=_async_update,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except BrainError as err:
        raise ConfigEntryNotReady from err

    # Секунды положить в update_interval, а не задавать в конструкторе:
    # так первый опрос происходит сразу, без лишнего ожидания
    coordinator.update_interval = DEFAULT_SCAN_INTERVAL

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "user_id": entry.data.get(CONF_USER_ID),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_update(hass: HomeAssistant) -> dict:
    """Один опрос: здоровье + последние запуски сканирований."""
    entry_data = _current(hass)
    client: BrainClient = entry_data["client"]

    try:
        health, runs = await client.health(), await client.scan_runs(limit=20)
    except BrainError as err:
        raise UpdateFailed(f"Ошибка связи с KumaFlow Brain: {err}") from err

    return {"health": health, "runs": runs or []}


def _current(hass: HomeAssistant) -> dict:
    """Данные единственной записи. Интеграция заточена на один мозг."""
    entries = hass.data.get(DOMAIN, {})
    if not entries:
        raise UpdateFailed("Нет загруженных записей KumaFlow Brain")
    return next(iter(entries.values()))


def active_run(runs: list[dict], phase: str) -> dict | None:
    """Наиболее свежий незавершённый запуск указанной фазы.

    scan_runs.status принимает queued/running/done/error
    (server/app/db/models.py:430-441).
    """
    for run in runs:
        if run.get("phase") == phase and run.get("status") in ("queued", "running"):
            return run
    return None


def latest_run(runs: list[dict], phase: str) -> dict | None:
    """Наиболее свежий запуск фазы в любом статусе — для «последнего результата»."""
    for run in runs:
        if run.get("phase") == phase:
            return run
    return None


def progress_pct(run: dict) -> float | None:
    """Процент из processed_items / total_items.

    total_items = 0 у только что созданного прогона, делить нельзя —
    возвращаем None, чтобы UI показал «нет данных», а не 0 %.
    """
    total = int(run.get("total_items") or 0)
    done = int(run.get("processed_items") or 0)
    if total <= 0:
        return None
    return round(done * 100.0 / total, 1)
