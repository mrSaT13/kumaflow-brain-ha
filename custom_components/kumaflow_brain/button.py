"""Кнопки KumaFlow Brain.

Главная из постановки — ручной запуск генерации ежедневного плейлиста.
Она сделана страховкой на случай, если встроенный крон не сработает.
Это подтверждается разбором: в deploy/docker-compose.yml сервиса
scheduler нет вообще, а timezone в CronTrigger не передаётся
(scheduler.py:46), так что джоб может сработать не в то время.

Кнопка бьёт в POST /api/playlists/generate-daily (server/app/api/playlists.py:205),
а не в POST /api/cron/{id}/run: крон-вариант отвечает {"queued": true}
и результата не возвращает (cron.py:98-104), а generate-daily выполняет
работу в текущем запросе. Иначе нажатие в HA ничего бы не сообщило.
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .api import BrainClient, BrainError
from .const import CONF_TOKEN_IS_ADMIN, CONF_USER_ID

_LOG = logging.getLogger(__name__)


class BrainButton(ButtonEntity):
    """Кнопка, вызывающая один эндпоинт мозга."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: BrainClient,
        key: str,
        name: str,
        icon: str,
        endpoint: str,
        json_body: dict | None = None,
        device_class: str | None = None,
    ) -> None:
        self.hass = hass
        self._client = client
        self._endpoint = endpoint
        self._json = json_body
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        # Короткий латинский id, чтобы в YAML писать
        # button.kf_generate_daily, а не транслитерацию кириллицы
        self._attr_suggested_object_id = f"kf_{key}"
        if device_class:
            self._attr_device_class = device_class
        self._entry = entry

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"KumaFlow Brain {self._entry.title}",
            "manufacturer": "KumaFlow",
            "model": "Brain",
        }

    async def async_press(self) -> None:
        try:
            result = await self._client.request(
                "POST", self._endpoint, json=self._json, timeout=600
            )
        except BrainError as err:
            raise HomeAssistantError(f"Мозг ответил ошибкой: {err}") from err

        _LOG.info("KumaFlow %s -> %s", self._endpoint, _brief(result))
        # Отдельного вызова обновления не делаем: координатор и так
        # перезапустит цикл, а долгая операция идёт минут.


def _brief(result) -> str:
    """Короткое человекочитаемое резюме ответа для лога."""
    if result is None:
        return "пустой ответ"
    if isinstance(result, dict):
        keep = ("status", "users", "ok", "playlist_id", "id", "queued", "job_id", "tracks")
        picked = {k: v for k, v in result.items() if k in keep}
        return repr(picked) if picked else f"ключи: {sorted(result)[:8]}"
    return repr(result)[:200]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    client: BrainClient = data["client"]
    user_id: str | None = data.get(CONF_USER_ID)
    is_admin: bool = bool(entry.data.get(CONF_TOKEN_IS_ADMIN))

    # Кнопки запуска задач в мозге помечены require_admin
    # (server/app/api/scan.py:98-156). Без админского токена они дают
    # 403 при каждом нажатии, поэтому не создаём их вовсе: отсутствие
    # кнопки понятнее, чем кнопка, которая всегда падает.
    if is_admin:
        entities: list[ButtonEntity] = [
            BrainButton(
                hass,
                entry,
                client,
                "scan_library",
                "Сканировать библиотеку",
                "mdi:folder-search",
                "/api/scan/library",
            ),
            BrainButton(
                hass,
                entry,
                client,
                "run_analysis",
                "Запустить sonic-анализ",
                "mdi:waveform",
                "/api/scan/analysis",
            ),
        ]
    else:
        _LOG.warning(
            "Кнопки запуска задач не созданы: токен без прав админа. "
            "Укажи BRAIN_API_TOKEN из окружения сервиса backend мозга."
        )
        entities = []

    # Дневной плейлист: generate-daily НЕ помечен require_admin,
    # поэтому кнопка работает с обычным токеном.
    entities.append(
        BrainButton(
            hass,
            entry,
            client,
            "generate_daily",
            "Сгенерировать дневной плейлист",
            "mdi:playlist-plus",
            "/api/playlists/generate-daily",
            json_body={"n": 30},
        )
    )

    # Волна требует user_id. Без него кнопка бессмысленна, поэтому
    # создаём её только если пользователь выбран в настройках.
    if user_id:
        entities.append(
            BrainButton(
                hass,
                entry,
                client,
                "my_wave",
                "Сгенерировать мою волну",
                "mdi:waves",
                "/api/wave/continue",
                json_body={"user_id": user_id, "queue": [], "count": 20, "settings": {}},
            )
        )

    async_add_entities(entities)
