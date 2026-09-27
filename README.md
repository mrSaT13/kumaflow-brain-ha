# KumaFlow Brain

[![hacs][hacs-badge]][hacs]
[![Home Assistant][ha-badge]][ha]
[![License][license-badge]](LICENSE)

Интеграция [KumaFlow Brain](https://github.com/mrSaT13/kumaflow-brain) для
Home Assistant: сенсоры прогресса фоновых задач и кнопки ручного запуска.

[hacs]: https://github.com/mrSaT13/kumaflow-brain-ha
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[ha]: https://www.home-assistant.io
[ha-badge]: https://img.shields.io/badge/Home%20Assistant-2024.8%2B-41BDF5.svg
[license-badge]: https://img.shields.io/badge/License-MIT-41BDF5.svg

[English](README.en.md) · Русский

---

Показывает, как продвигаются сканирование библиотеки, sonic-анализ,
эмбеддинги и кластеризация — и позволяет запускать их вручную.

Работает поверх готового API мозга, без изменений на стороне KumaFlow
Brain. Внешних зависимостей нет.

## Возможности

### Сенсоры

17 сенсоров от одного устройства **KumaFlow Brain**.

Общие:

| entity_id | Описание |
|---|---|
| `sensor.kf_health` | доступность мозга: `1` — отвечает, `0` — нет |
| `sensor.kf_tracks` | треков в библиотеке |

Прогресс фоновых задач — по три сенсора на фазу:

| entity_id | Описание |
|---|---|
| `sensor.kf_library_progress` | сканирование библиотеки, % |
| `sensor.kf_library_status` | статус прогона: `queued` / `running` / `done` / `error` |
| `sensor.kf_library_finished` | время окончания |
| `sensor.kf_analysis_progress` | sonic-анализ, % |
| `sensor.kf_analysis_status` | статус sonic-анализа |
| `sensor.kf_analysis_finished` | время окончания |
| `sensor.kf_clap_progress` | CLAP-эмбеддинги, % |
| `sensor.kf_clap_status` | статус |
| `sensor.kf_clap_finished` | время окончания |
| `sensor.kf_lyrics_progress` | тексты треков, % |
| `sensor.kf_lyrics_status` | статус |
| `sensor.kf_lyrics_finished` | время окончания |
| `sensor.kf_clusters_progress` | кластеризация, % |
| `sensor.kf_clusters_status` | статус |
| `sensor.kf_clusters_finished` | время окончания |

У прогресса есть атрибуты `phase`, `status`, `running`,
`processed_items`, `total_items`, `error` — из них удобно строить
дашборд.

Прогресс считается как `processed_items / total_items`. Пока задача
только создана и `total_items` ещё 0, значение — `None`, а не 0 %,
чтобы в дашборде не мигали нули.

### Кнопки

| entity_id | Действие |
|---|---|
| `button.kf_generate_daily` | сгенерировать дневной плейлист |
| `button.kf_scan_library` | сканировать библиотеку |
| `button.kf_run_analysis` | запустить sonic-анализ |
| `button.kf_my_wave` | сгенерировать «Мою волну» (нужен ID пользователя) |

### Сервисы

Для автоматизаций YAML:

| service | Действие |
|---|---|
| `kumaflow_brain.generate_daily` | дневной плейлист, `n` треков (по умолчанию 30) |
| `kumaflow_brain.my_wave` | волна, `count`, `mood`, `activity` |
| `kumaflow_brain.start_scan` | запуск скана, `kind`: `library` / `analysis` |

## Установка

### Через HACS

1. Открой **HACS → Интеграции → ⋮ → Добавить вручную**
2. Вставь адрес репозитория:
   `https://github.com/mrSaT13/kumaflow-brain-ha`
3. Открой **HACS → Интеграции**, найди **KumaFlow Brain**,
   нажми **Скачать**
4. **Перезагрузи Home Assistant**

### Вручную

Скопируй папку `custom_components/kumaflow_brain` в
`<config>/custom_components/` и перезагрузи Home Assistant:

```bash
cp -r custom_components/kumaflow_brain <config>/custom_components/
```

## Настройка

**Настройки → Устройства и службы → Добавить интеграцию → KumaFlow Brain**

| Поле | Значение | Обязательно |
|---|---|---|
| Адрес мозга | `http://<хост>:8000` | да |
| Токен | `BRAIN_API_TOKEN` | да |
| ID пользователя | ID юзера из профиля | нет |

Токен берётся из переменной `BRAIN_API_TOKEN` в окружении сервиса
`backend` либо создаётся в веб-интерфейсе мозга
(Настройки → API-токены).

> **Нужен токен со скоупом `admin`.** Настройка сохранится и с обычным
> токеном — проверка соединения идёт по `/api/status/health`, который
> доступен всем. Но кнопки работают на запись и получат `403`.

`ID пользователя` нужен только для кнопки «Моя волна». Возьми его из
адреса страницы волны в веб-интерфейсе мозга или из
`GET /api/users/`.

Связь проверяется при вводе: если адрес или токен неверны, мастер
покажет ошибку и ничего не сохранит.

## Использование

### Карточка

```yaml
type: vertical-stack
cards:
  - type: entities
    title: KumaFlow Brain
    show_header_toggle: false
    entities:
      - entity: sensor.kf_health
        name: Мозг на связи
      - entity: sensor.kf_tracks
        name: Треков
      - type: divider
      - entity: sensor.kf_library_progress
        name: Сканирование
        type: gauge:
          severity: green
          min: 0
          max: 100
      - entity: sensor.kf_analysis_progress
        name: Sonic-анализ
        type: gauge:
          severity: green
          min: 0
          max: 100

  - type: grid
    cards:
      - type: button
        entity: button.kf_generate_daily
        name: Дневной плейлист
        show_name: true
        layout_options:
          grid_columns: 3
          grid_rows: 1
      - type: button
        entity: button.kf_scan_library
        name: Сканировать
        show_name: true
        layout_options:
          grid_columns: 3
          grid_rows: 1
      - type: button
        entity: button.kf_run_analysis
        name: Sonic-анализ
        show_name: true
        layout_options:
          grid_columns: 3
          grid_rows: 1
```

### Автоматизация

```yaml
alias: KumaFlow — дневной плейлист
mode: single
triggers:
  - platform: time
    at: "07:30:00"
  - platform: state
    entity_id: sensor.kf_health
    to: "1"
conditions:
  - condition: state
    entity_id: sensor.kf_analysis_status
    state: done
actions:
  - service: button.press
    target:
      entity_id: button.kf_generate_daily
```

Второй триггер нужен для случая, когда Home Assistant запустился после
мозга: сенсор доступности станет `1` и автоматизация отработает.

## Как это работает

Интеграция опрашивает мозг раз в 15 секунд — тот же интервал, что
использует веб-интерфейс KumaFlow Brain. Используемые эндпоинты:

| Эндпоинт | Зачем |
|---|---|
| `GET /api/status/health` | проверка связи при настройке, датчик доступности |
| `GET /api/scan/runs` | прогресс и статусы фоновых задач |
| `POST /api/scan/library` | кнопка сканирования |
| `POST /api/scan/analysis` | кнопка sonic-анализа |
| `POST /api/playlists/generate-daily` | кнопка дневного плейлиста |
| `POST /api/wave/continue` | кнопка «Моя волна» |

Кнопка дневного плейлиста обращается к `generate-daily`, а не к
`/api/cron/{id}/run`: первый выполняет работу в текущем запросе и
возвращает результат, второй только ставит задачу в очередь RQ и
отвечает `{"queued": true}`. Для кнопки важна обратная связь, поэтому
выбран первый. Операция занимает минуты, таймаут клиента — 600 с.

## Ограничения

- **Кнопка «Моя волна»** появляется, только если заполнен
  `ID пользователя`
- **Нет сенсоров «сейчас играет»** — в мозге есть `/api/now-playing`,
  но интеграция его не читает
- **Нет графиков** — `long-term statistics` не реализованы
- **Обновление раз в 15 секунд** — сенсоры не пушат изменения,
  HA видит их по опросу

## Требования

- Home Assistant **2024.8** или новее
- KumaFlow Brain с доступным `GET /api/status/health`
- Токен со скоупом `admin` — для кнопок

Внешние зависимости не добавляются: используется `aiohttp` из ядра HA.

## Разработка

```bash
git clone https://github.com/mrSaT13/kumaflow-brain-ha
cd kumaflow-brain-ha
```

Структура:

```
custom_components/kumaflow_brain/
├── __init__.py       координатор, платформы
├── config_flow.py    мастер настройки
├── api.py            асинхронный клиент мозга
├── sensor.py         сенсоры
├── button.py         кнопки
├── const.py          домен, дефолты, фазы
└── services.yaml     сервисы для автоматизаций
```

Добавить сенсор новой фазы: добавить константу в `const.py`, затем
кортеж в `RUN_SENSOR_SETS` в `sensor.py` и ключ в `icons/icon.json`.
Ключи в `icon.json` должны совпадать с ключами в коде.

## Лицензия

MIT — см. [LICENSE](LICENSE).

Иконка взята из проекта
[KumaFlow Brain](https://github.com/mrSaT13/kumaflow-brain)
(`web/public/icon-512.png`), уменьшена до 256×256.

Проблемы и предложения — в
[issues](https://github.com/mrSaT13/kumaflow-brain-ha/issues).
