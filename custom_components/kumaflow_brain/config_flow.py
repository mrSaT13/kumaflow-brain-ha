"""Мастер настройки: URL + токен + выбор пользователя."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import BrainClient, BrainError
from .const import CONF_TOKEN, CONF_TOKEN_IS_ADMIN, CONF_URL, CONF_USER_ID, DOMAIN

_LOG = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="http://localhost:8000"): str,
        vol.Required(CONF_TOKEN): str,
        vol.Optional(CONF_USER_ID): str,
    }
)


class BrainConfigFlow(ConfigFlow, domain=DOMAIN):
    """Одношаговый мастер с проверкой соединения."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            token = user_input[CONF_TOKEN].strip()
            user_id = (user_input.get(CONF_USER_ID) or "").strip() or None

            session = async_create_clientsession(self.hass)
            client = BrainClient(url, token, session)

            try:
                await client.health()
            except BrainError as err:
                _LOG.debug("Проверка соединения не удалась: %s", err)
                errors["base"] = "cannot_connect"
                return self.async_show_form(
                    step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
                )

            # Проверяем права сразу, на настройке. Кнопки запуска задач
            # требуют админского токена, и без проверки пользователь
            # узнаёт об этом только при нажатии — из сообщения "403",
            # которое ни о чём не говорит.
            try:
                is_admin = await client.probe_admin()
            except BrainError as err:
                _LOG.debug("Не удалось определить права: %s", err)
                is_admin = False

            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()

            if not is_admin:
                _LOG.warning(
                    "Токен без прав админа: кнопки запуска задач будут "
                    "возвращать 403. Нужен BRAIN_API_TOKEN из окружения "
                    "сервиса backend мозга — токены из веб-интерфейса "
                    "админом не являются (server/app/core/auth.py)."
                )

            return self.async_create_entry(
                title=f"KumaFlow Brain ({_host_of(url)})",
                data={
                    CONF_URL: url,
                    CONF_TOKEN: token,
                    CONF_USER_ID: user_id,
                    CONF_TOKEN_IS_ADMIN: is_admin,
                },
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)


def _host_of(url: str) -> str:
    cleaned = url.replace("http://", "").replace("https://", "").strip("/")
    return cleaned or url
