"""Мастер настройки: URL + токен + выбор пользователя."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import BrainClient, BrainError
from .const import CONF_TOKEN, CONF_URL, CONF_USER_ID, DOMAIN

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
                health = await client.health()
            except BrainError as err:
                _LOG.debug("Проверка соединения не удалась: %s", err)
                errors["base"] = "cannot_connect"
            else:
                # Токен без прав админа пройдёт /health, но кнопки и
                # запуск скана потом упрутся в 403. Поэтому заранее
                # предупреждаем, но настройку не блокируем.
                if not _has_admin(health):
                    _LOG.warning(
                        "Токен прошёл проверку, но не выглядит админским. "
                        "Кнопки запуска и просмотр чужих профилей могут быть недоступны."
                    )
                await self.async_set_unique_id(url)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"KumaFlow Brain ({_host_of(url)})",
                    data={CONF_URL: url, CONF_TOKEN: token, CONF_USER_ID: user_id},
                )

            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)


def _host_of(url: str) -> str:
    cleaned = url.replace("http://", "").replace("https://", "").strip("/")
    return cleaned or url


def _has_admin(health: dict[str, Any]) -> bool:
    """/health в мозгу (server/app/api/status.py:7) может отдавать роль.

    Если поля нет — считаем, что всё в порядке: отсутствие информации
    не повод блокировать настройку.
    """
    if not isinstance(health, dict):
        return True
    for key in ("role", "scope", "scopes", "is_admin", "admin"):
        if key in health:
            value = health[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("admin", "true", "1")
            if isinstance(value, (list, tuple)):
                return "admin" in {str(v).lower() for v in value}
    return True
