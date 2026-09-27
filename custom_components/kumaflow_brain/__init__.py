"""Интеграция KumaFlow Brain для Home Assistant.

Что даёт:
  * сенсоры прогресса сканирования библиотеки и sonic-анализа
  * кнопки ручного запуска дневного плейлиста, волны и задач
  * прогресс CLAP-эмбеддингов, текстов треков и кластеризации

Структура координатора сделана подклассом, а не через update_method:
  * update_method вызывается как await self.update_method(), БЕЗ
    аргументов — функция с параметром hass роняет настройку с
    "missing 1 required positional argument";
  * подкласс держит клиента у себя, поэтому первый опрос не зависит
    от порядка записи в hass.data. При update_method пришлось бы сначала
    наполнить hass.data, а потом обновляться, иначе первый опрос падает.

Клиент лежит на координаторе, а не в hass.data[DOMAIN][entry_id] ещё и
потому, что при нескольких записях (несколько адресов мозга) каждый
координатор работает со своим адресом, а не с первым попавшимся.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BrainClient, BrainError
from .const import CONF_TOKEN, CONF_URL, CONF_USER_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOG = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


class BrainCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Опрашивает мозг и раздаёт результат платформам."""

    def __init__(self, hass: HomeAssistant, client: BrainClient, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOG,
            # Имя с entry_id: при двух записях их не спутать в логах
            name=f"{DOMAIN} {entry.entry_id[:8]}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self._client = client
        self._entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Один опрос: доступность + последние запуски задач.

        HA сам вызывает этот метод, аргументов не передаёт. Любое
        BrainError превращаем в UpdateFailed, иначе HA покажет
        «Unexpected error» вместо понятного «не удалось обновить».
        """
        try:
            health, runs = await self._client.health(), await self._client.scan_runs(limit=20)
        except BrainError as err:
            # Отдаём текст ошибки, а не голую строку: по нему видно,
            # это 404, 401 или таймаут — три разные причины
            raise UpdateFailed(f"Ошибка связи с KumaFlow Brain: {err}") from err

        return {"health": health or {}, "runs": runs or []}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_create_clientsession(hass)
    client = BrainClient(entry.data[CONF_URL], entry.data[CONF_TOKEN], session)

    coordinator = BrainCoordinator(hass, client, entry)

    # Первый опрос делаем сразу: если мозг недоступен, запись встанет в
    # ожидание и HA покажет «Не удалось настроить. Повторная попытка»
    # вместо молчаливых пустых сенсоров
    await coordinator.async_config_entry_first_refresh()

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
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


def active_run(runs: list[dict], phase: str) -> dict | None:
    """Наиболее свежий незавершённый запуск указанной фазы.

    scan_runs.status принимает queued/running/done/error
    (server/app/db/models.py:430-441, сверено с исходниками).
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
    try:
        total = int(run.get("total_items") or 0)
        done = int(run.get("processed_items") or 0)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return round(min(done, total) * 100.0 / total, 1)
