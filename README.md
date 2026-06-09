# AA PI Tracker

[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![Alliance Auth](https://img.shields.io/badge/alliance--auth-5.0+-orange)](https://gitlab.com/allianceauth/allianceauth)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-green)](LICENSE)

An [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) plugin to track EVE Online Planetary Interaction colonies — extractor expiry, factory output, and multi-character production planning.

---

## Features

- **Characters** — Register multiple EVE characters per user; PI data is synced automatically from ESI on a configurable schedule
- **Extractors** — Cross-character overview of all active extractors with expiry time, cycle time, output rate (units/h), and a progress bar showing time remaining
- **Planets** — Per-planet view with planet type, upgrade level, active extractors and factories, and project assignment
- **Projects** — Define a production target (e.g. "10 Broadcast Nodes/h"), automatically expand the full P1→P4 factory and extraction chain, and track actual vs. required factories and extraction rates for each assigned planet
- **No SDE dependency** — All PI production data (P0 resources, P1–P4 recipes, factory cycle times) is bundled as static Python data; no external database required
- Celery Beat task registers automatically on startup — no `CELERYBEAT_SCHEDULE` entry in `local.py` required

---

## Requirements

| Requirement | Version |
|---|---|
| Alliance Auth | >= 5.0 |
| Python | >= 3.10 |
| django-esi | >= 4.0 |

### ESI Scope

| Scope | Used for |
|---|---|
| `esi-planets.manage_planets.v1` | Planet list and pin details (extractors, factories) per character |

> **Note:** Despite the scope name, only read endpoints are used — no modifications are made to in-game PI colonies.

---

## Installation

**Step 1 — Install the package**

    pip install git+https://github.com/GurkeTonic/aa-pi-tracker.git

**Step 2 — Add to `INSTALLED_APPS` in `local.py`**

    INSTALLED_APPS += [
        'aa_pi_tracker',
    ]

**Step 3 — Add ESI contact e-mail to `local.py`**

Required by CCP for the ESI User-Agent header:

    ESI_USER_CONTACT_EMAIL = "your@email.com"

**Step 4 — Run migrations and collect static**

    python manage.py migrate
    python manage.py collectstatic --noinput

**Step 5 — Restart services**

    sudo supervisorctl restart myauth:

---

## Setup

1. Open **PI Tracker** in the Alliance Auth navigation menu
2. Go to the **Characters** tab and click **Add Character**
3. Authenticate through ESI SSO — the `esi-planets.manage_planets.v1` scope is requested
4. The first sync starts immediately after authorisation; subsequent syncs run on the configured interval

Multiple characters per user are supported. Each character is synced independently.

---

## Permissions

| Permission | Description |
|---|---|
| `aa_pi_tracker.view_pi` | Access to all PI Tracker tabs |

Assign via **Django Admin → Auth → Groups** or per state.

---

## Settings

Add to `myauth/settings/local.py` to override defaults:

| Setting | Default | Description |
|---|---|---|
| `AA_PI_TRACKER_SYNC_INTERVAL` | `60` | Sync interval in minutes. The beat schedule uses `apply_offset` to spread load. Override the entire schedule entry in `CELERYBEAT_SCHEDULE` if needed. |
| `ESI_USER_CONTACT_EMAIL` | — | **Required.** Included in every ESI request as part of the User-Agent. |

---

## Tabs

**Characters** — Registered ESI characters with planet count and last sync time. Add or remove characters, trigger a manual sync.

**Extractors** — All active extractor pins across all characters, sorted by character. Shows product, expiry time, cycle time, output in units/h, and a progress bar. Expired extractors are highlighted.

**Planets** — All planets across all characters. Shows planet type, upgrade level, extractor products, factory schematics, and which project the planet is assigned to.

**Projects** — User-defined production targets. Select a schematic and a target output rate; the module calculates the full factory chain (how many P1, P2, P3 factories are needed) and the required raw extraction rate. Assign planets to a project to compare actual vs. required capacity.

---

## Technical Notes

- PI production chain data (recipes, tier levels, cycle times, input quantities) is hardcoded in `aa_pi_tracker/schematics.py` based on in-game values — no EVE SDE installation required
- Unknown type IDs fall back to ESI (`/v3/universe/types/{id}`) with a 24-hour cache; unknown schematic IDs fall back to `/v1/universe/schematics/{id}`
- ESI responses are cached respecting the `Expires` header; minimum TTL is 60 seconds

---

## Contributing

Pull requests are welcome. For major changes please open an issue first.

---

## License

[GPL-3.0](LICENSE)
