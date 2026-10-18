# STVR Archive for Stremio (experimental)

Unofficial, experimental Docker Stremio addon based on the STVR public archive endpoints documented by the Kodi addon.

## Credits and licensing

Based on research and endpoint mappings in [plugin.video.rtvs.sk](https://github.com/xbmc-kodi-cz/plugin.video.rtvs.sk).
Original Kodi implementation copyright (C) Maros Ondrasek (2013/2014), updated by Jastrab (2022 and later).
Original Kodi source: GPL-2.0-or-later. This independent port is also provided under GPL-2.0-or-later (see LICENSE).
Not affiliated with STVR. No DRM circumvention or content hosting.

## Run

```bash
docker compose up -d --build
curl http://127.0.0.1:7000/manifest.json
curl http://127.0.0.1:7000/catalog/series/stvr-az/genre=A.json
```

Localhost-only binding is deliberate. For external clients, publish behind your existing HTTPS reverse proxy (Caddy / Traefik), with appropriate access restrictions. Install `https://your-host/manifest.json` in Stremio.

## Limitations

- Untested against live STVR due to network restrictions in development environment.
- A–Z catalog starts on A by default and uses Stremio genre selector for letters.
- No global search, radio, live TV, or release-year grouping yet.
- Large shows are capped at 20 × 1000 returned entries to avoid unbounded requests.
- Some streams can be geo-restricted, expired, protected or require headers.
- Remux integration has not been tested.
- The source Kodi plugin is **not** vendored or forked here. This is a standalone first port; a proper GitHub fork requires repository creation rights/tools.
