"""Асинхронный клиент API KumaFlow Brain.

Эндпоинты сверены с kumaflow-brain-main 0.2.4:
  GET  /api/health            server/app/api/status.py:7
  GET  /api/scan/runs                server/app/api/scan.py
  POST /api/scan/library             запуск сканирования библиотеки
  POST /api/scan/analysis            запуск sonic-анализа
  POST /api/playlists/generate-daily server/app/api/playlists.py:205
  POST /api/wave/continue            server/app/api/wave.py
  GET  /api/users/{id}/profile       server/app/api/users.py

Авторизация: Bearer-токен. В мозге это либо BRAIN_API_TOKEN из окружения
(роль admin), либо токен из таблицы api_tokens со скоупами
(server/app/core/auth.py, models.py:523).
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_TIMEOUT, LONG_TIMEOUT

_LOG = logging.getLogger(__name__)


class BrainError(Exception):
    """Ошибка обращения к мозгу."""


class BrainClient:
    """Тонкая обёртка над aiohttp без привязки к HA."""

    def __init__(self, url: str, token: str, session: aiohttp.ClientSession) -> None:
        self._base = url.rstrip("/")
        self._token = token
        self._session = session

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
        }

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        timeout: int = API_TIMEOUT,
    ) -> Any:
        url = f"{self._base}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers(),
                json=json,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    raise BrainError(f"{method} {path} -> HTTP {resp.status}: {body[:300]}")
                if not body:
                    return None
                try:
                    return await resp.json(content_type=None)
                except Exception:  # noqa: BLE001 — ответ может быть не JSON
                    return {"_raw": body}
        except aiohttp.ClientError as exc:
            raise BrainError(f"{method} {path} -> {exc}") from exc

    # --- служебное -------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        return await self.request("GET", "/api/health")

    async def scan_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        """Последние запуски. Формат ответа — {runs: [...]}."""
        data = await self.request("GET", f"/api/scan/runs?limit={limit}")
        if isinstance(data, dict):
            return data.get("runs") or []
        return data or []

    async def start_library_scan(self) -> Any:
        return await self.request("POST", "/api/scan/library", timeout=LONG_TIMEOUT)

    async def start_analysis(self) -> Any:
        return await self.request("POST", "/api/scan/analysis", timeout=LONG_TIMEOUT)

    async def generate_daily(self, n: int = 30) -> Any:
        """Синхронный вариант, в отличие от POST /api/cron/{id}/run.

        Cron-вариант отвечает {"queued": true} и результата не возвращает
        (server/app/api/cron.py:98-104), а generate-daily выполняет работу
        в текущем запросе (playlists.py:205-210). Для кнопки в HA нужен
        именно он — иначе нажатие ничего не сообщит.
        """
        return await self.request(
            "POST", "/api/playlists/generate-daily", json={"n": n}, timeout=LONG_TIMEOUT
        )

    async def wave_continue(
        self,
        user_id: str,
        *,
        count: int = 20,
        settings: dict[str, Any] | None = None,
    ) -> Any:
        return await self.request(
            "POST",
            "/api/wave/continue",
            json={
                "user_id": user_id,
                "queue": [],
                "count": count,
                "settings": settings or {},
            },
            timeout=LONG_TIMEOUT,
        )

    async def user_ids(self) -> list[dict[str, Any]]:
        data = await self.request("GET", "/api/users/")
        if isinstance(data, dict):
            return data.get("users") or []
        return data or []
