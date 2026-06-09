# aa-pi-tracker

Alliance Auth plugin for EVE Online Planetary Interaction planning.

## Features

- Track PI extractors and factories across multiple characters
- Monitor extractor expiry times
- Plan production projects with gap analysis

## Installation

```bash
pip install aa-pi-tracker
```

Add `"aa_pi_tracker"` to `INSTALLED_APPS` in your `local.py`.

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `AA_PI_TRACKER_SYNC_INTERVAL` | `60` | Sync interval in minutes |
| `ESI_USER_CONTACT_EMAIL` | — | Required for ESI User-Agent |
