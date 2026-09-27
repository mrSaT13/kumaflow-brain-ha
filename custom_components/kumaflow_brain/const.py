"""Константы интеграции KumaFlow Brain."""

from __future__ import annotations

DOMAIN = "kumaflow_brain"

# Атрибуты runtime-данных в hass.data[DOMAIN][entry_id]
CONF_URL = "url"
CONF_TOKEN = "token"
CONF_USER_ID = "user_id"

# Как долго ждём между обновлениями координатора. Мозг — локальная сеть,
# поэтому 15 с достаточно: это тот же интервал, что уже использует сам
# веб-интерфейс мозга (web/src/components/NowPlaying.tsx:24).
DEFAULT_SCAN_INTERVAL = 15

# Таймаут HTTP-запросов. Генерация дневного плейлиста занимает минуты,
# поэтому для кнопок отдельный, увеличенный.
API_TIMEOUT = 30
LONG_TIMEOUT = 600

# Фаза scan_runs. Значения сверены с server/app/api/scan.py.
PHASE_LIBRARY = "library"
PHASE_ANALYSIS = "analysis"
PHASE_CLAP = "clap"
PHASE_LYRICS = "lyrics"
PHASE_CLUSTERS = "clusters"
PHASE_COLLAB = "collab"
PHASE_SMART = "smart"
