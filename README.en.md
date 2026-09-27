# KumaFlow Brain

[![hacs][hacs-badge]][hacs]
[![Home Assistant][ha-badge]][ha]
[![License][license-badge]](LICENSE)

Home Assistant integration for
[KumaFlow Brain](https://github.com/mrSaT13/kumaflow-brain): progress
sensors for background jobs and buttons to start them manually.

[hacs]: https://github.com/mrSaT13/kumaflow-brain-ha
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[ha]: https://www.home-assistant.io
[ha-badge]: https://img.shields.io/badge/Home%20Assistant-2024.8%2B-41BDF5.svg
[license-badge]: https://img.shields.io/badge/License-MIT-41BDF5.svg

[Русский](README.md) · English

---

Reports how library scanning, sonic analysis, embeddings and clustering
are progressing, and lets you start them by hand.

Works against the existing KumaFlow Brain API — no changes required on the
brain side. No extra dependencies.

## Features

### Sensors

17 sensors on a single **KumaFlow Brain** device.

General:

| entity_id | Description |
|---|---|
| `sensor.kf_health` | brain availability: `1` up, `0` down |
| `sensor.kf_tracks` | tracks in the library |

Background jobs — three sensors per phase:

| entity_id | Description |
|---|---|
| `sensor.kf_library_progress` | library scan, % |
| `sensor.kf_library_status` | job status: `queued` / `running` / `done` / `error` |
| `sensor.kf_library_finished` | finish time |
| `sensor.kf_analysis_progress` | sonic analysis, % |
| `sensor.kf_analysis_status` | sonic analysis status |
| `sensor.kf_analysis_finished` | finish time |
| `sensor.kf_clap_progress` | CLAP embeddings, % |
| `sensor.kf_clap_status` | status |
| `sensor.kf_clap_finished` | finish time |
| `sensor.kf_lyrics_progress` | lyrics fetching, % |
| `sensor.kf_lyrics_status` | status |
| `sensor.kf_lyrics_finished` | finish time |
| `sensor.kf_clusters_progress` | clustering, % |
| `sensor.kf_clusters_status` | status |
| `sensor.kf_clusters_finished` | finish time |

Progress sensors expose `phase`, `status`, `running`,
`processed_items`, `total_items` and `error` as attributes, which are
useful for custom dashboards.

Progress is `processed_items / total_items`. While a job has just been
created and `total_items` is still 0, the value is `None` rather than
0 % — so dashboards don't flash zeros.

### Buttons

| entity_id | Action |
|---|---|
| `button.kf_generate_daily` | generate the daily playlist |
| `button.kf_scan_library` | scan the library |
| `button.kf_run_analysis` | start sonic analysis |
| `button.kf_my_wave` | generate My Wave (requires a user ID) |

### Services

For YAML automations:

| service | Action |
|---|---|
| `kumaflow_brain.generate_daily` | daily playlist, `n` tracks (default 30) |
| `kumaflow_brain.my_wave` | wave, `count`, `mood`, `activity` |
| `kumaflow_brain.start_scan` | start a scan, `kind`: `library` / `analysis` |

## Installation

### HACS

1. Open **HACS → Integrations → ⋮ → Add custom repository**
2. Enter the repository URL:
   `https://github.com/mrSaT13/kumaflow-brain-ha`
3. Open **HACS → Integrations**, find **KumaFlow Brain**, click
   **Download**
4. **Restart Home Assistant**

### Manual

Copy `custom_components/kumaflow_brain` into `<config>/custom_components/`
and restart Home Assistant:

```bash
cp -r custom_components/kumaflow_brain <config>/custom_components/
```

## Configuration

**Settings → Devices & services → Add integration → KumaFlow Brain**

| Field | Value | Required |
|---|---|---|
| Brain URL | `http://<host>:8000` | yes |
| Token | `BRAIN_API_TOKEN` | yes |
| User ID | user id from the profile | no |

The token comes from the `BRAIN_API_TOKEN` environment variable of the
`backend` service, or can be created in the brain web UI under
Settings → API tokens.

> **A token with the `admin` scope is required.** Configuration will be
> saved with a regular token too — the connection check uses
> `/api/status/health`, which anyone may call. But the buttons write
> and will return `403`.

`User ID` is only needed for the My Wave button. Take it from the wave
page URL in the brain web UI, or from `GET /api/users/`.

Connectivity is verified as you type: if the URL or token is wrong, the
config flow shows an error and saves nothing.

## Usage

### Card

```yaml
type: vertical-stack
cards:
  - type: entities
    title: KumaFlow Brain
    show_header_toggle: false
    entities:
      - entity: sensor.kf_health
        name: Brain online
      - entity: sensor.kf_tracks
        name: Tracks
      - type: divider
      - entity: sensor.kf_library_progress
        name: Library scan
        type: gauge:
          severity: green
          min: 0
          max: 100
      - entity: sensor.kf_analysis_progress
        name: Sonic analysis
        type: gauge:
          severity: green
          min: 0
          max: 100

  - type: grid
    cards:
      - type: button
        entity: button.kf_generate_daily
        name: Daily playlist
        show_name: true
        layout_options:
          grid_columns: 3
          grid_rows: 1
      - type: button
        entity: button.kf_scan_library
        name: Scan library
        show_name: true
        layout_options:
          grid_columns: 3
          grid_rows: 1
      - type: button
        entity: button.kf_run_analysis
        name: Sonic analysis
        show_name: true
        layout_options:
          grid_columns: 3
          grid_rows: 1
```

### Automation

```yaml
alias: KumaFlow daily playlist
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

The second trigger covers the case where Home Assistant starts after the
brain: the availability sensor turns `1` and the automation fires.

## How it works

The integration polls the brain every 15 seconds — the same interval the
KumaFlow Brain web UI uses. Endpoints used:

| Endpoint | Purpose |
|---|---|
| `GET /api/status/health` | connection check, availability sensor |
| `GET /api/scan/runs` | progress and status of background jobs |
| `POST /api/scan/library` | scan button |
| `POST /api/scan/analysis` | analysis button |
| `POST /api/playlists/generate-daily` | daily playlist button |
| `POST /api/wave/continue` | My Wave button |

The daily playlist button calls `generate-daily` rather than
`/api/cron/{id}/run`: the former does the work in the current request
and returns the result, the latter only enqueues an RQ job and answers
`{"queued": true}`. A button should give feedback, so the first one is
used. It takes minutes, hence the 600 s client timeout.

## Limitations

- The **My Wave button** only appears if a `User ID` is configured
- **No now-playing sensors** — the brain has `/api/now-playing`, but the
  integration does not read it
- **No long-term statistics** — graphs are not implemented
- **15 second update interval** — sensors don't push; HA polls

## Requirements

- Home Assistant **2024.8** or newer
- KumaFlow Brain with a reachable `GET /api/status/health`
- A token with the `admin` scope, for the buttons

No extra dependencies: uses `aiohttp` from the HA core.

## Development

```bash
git clone https://github.com/mrSaT13/kumaflow-brain-ha
cd kumaflow-brain-ha
```

Layout:

```
custom_components/kumaflow_brain/
├── __init__.py       coordinator, platforms
├── config_flow.py    config flow
├── api.py            async brain client
├── sensor.py         sensors
├── button.py         buttons
├── const.py          domain, defaults, phases
└── services.yaml     services for automations
```

To add a sensor for a new phase: add a constant to `const.py`, then a
tuple to `RUN_SENSOR_SETS` in `sensor.py`, then the key to
`icons/icon.json`. Keys in `icon.json` must match the keys used in code.

## License

MIT — see [LICENSE](LICENSE).

The icon comes from the
[KumaFlow Brain](https://github.com/mrSaT13/kumaflow-brain) project
(`web/public/icon-512.png`), downscaled to 256×256.

Issues and feature requests:
[issues](https://github.com/mrSaT13/kumaflow-brain-ha/issues).
