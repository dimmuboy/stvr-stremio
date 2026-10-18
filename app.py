"""STVR archive Stremio bridge.

Inspired by plugin.video.rtvs.sk, copyright Maros Ondrasek and Jastrab.
The original project is licensed under GPL-2.0-or-later.
"""
import base64
import html
import os
import re
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request
from cachetools import TTLCache

BASE = "https://www.stvr.sk"
app = Flask(__name__)
cache = TTLCache(maxsize=1024, ttl=900)
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; STVR-Stremio/0.1)"})


def fetch(path, as_json=False):
    url = urljoin(BASE, path)
    if not url.startswith(BASE + "/"):
        raise ValueError("Unsupported STVR URL")
    key = (url, as_json)
    if key not in cache:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        cache[key] = response.json() if as_json else response.text
    return cache[key]


def encode(value):
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()


def id_for(path):
    return "stvr:" + encode(path)


def path_from_id(value):
    if not value.startswith("stvr:"):
        raise ValueError("Invalid ID")
    path = decode(value[5:])
    if not re.fullmatch(r"/televizia/archiv/\d+/\d+", path):
        raise ValueError("Invalid archive path")
    return path


def listings(letter):
    page = fetch("/televizia/archiv?l=" + quote(letter) + "&ord=az")
    soup = BeautifulSoup(page, "html.parser")
    entries = []
    seen = set()
    for item in soup.select(".tv-archiv__item"):
        anchor = item.select_one('a[href*="/televizia/archiv/"]')
        if not anchor:
            continue
        path = anchor.get("href", "").split("?", 1)[0]
        path = "/" + path.lstrip("/") if not path.startswith("http") else path.replace(BASE, "")
        if not re.fullmatch(r"/televizia/archiv/\d+/\d+", path) or path in seen:
            continue
        seen.add(path)
        title_el = item.find(["h2", "h3"])
        title = title_el.get_text(" ", strip=True) if title_el else anchor.get("title", "")
        image = item.select_one("img")
        thumb = image.get("src") if image else None
        data = {"id": id_for(path), "type": "series", "name": title or "STVR relácia"}
        if thumb:
            data["poster"] = urljoin(BASE, thumb)
        entries.append(data)
    return entries


def episodes(path):
    node, program = path.rsplit("/", 2)[-2:]
    page = fetch(path)
    soup = BeautifulSoup(page, "html.parser")
    selection = soup.select_one("#filter_series")
    series_ids = [x.get("value") for x in selection.select("option[value]")] if selection else []
    selected = series_ids[0] if series_ids else node
    if not selected or not selected.isdigit():
        selected = node
    results = []
    page_num = 1
    while page_num <= 20:
        data = fetch(f"/json/tv/archiv?e=1&archive=1&p={page_num}&l=1000&o=desc&s={selected}", as_json=True)
        programs = data.get("program") or []
        for program_data in programs:
            video_id = str(program_data.get("ID") or "")
            if not video_id.isdigit():
                continue
            air = program_data.get("air") or ""
            video = {
                "id": f"stvrvideo:{video_id}",
                "title": program_data.get("name") or air or "Epizóda",
                "released": air.replace(" ", "T", 1) + ":00Z" if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", air) else None,
                "overview": program_data.get("description") or program_data.get("synopsis") or "",
            }
            if program_data.get("image"):
                video["thumbnail"] = urljoin(BASE, program_data["image"])
            video = {k: v for k, v in video.items() if v is not None}
            results.append(video)
        total = int((data.get("paging") or {}).get("results") or 0)
        if not programs or (total and page_num * 1000 >= total) or len(programs) < 1000:
            break
        page_num += 1
    return results


MANIFEST = {
    "id": "community.stvr.archive", "version": "0.1.0", "name": "STVR Archive",
    "description": "Unofficial STVR television archive. Based on research from Kodi RTVS addon by Maros Ondrasek and Jastrab.",
    "resources": ["catalog", "meta", "stream"], "types": ["series"],
    "idPrefixes": ["stvr:", "stvrvideo:"],
    "catalogs": [{"type": "series", "id": "stvr-az", "name": "STVR A–Z",
                  "extra": [{"name": "genre", "options": ["0-9"] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "optionsLimit": 1}]}],
}


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.get("/manifest.json")
def manifest():
    return jsonify(MANIFEST)


@app.get("/catalog/series/stvr-az.json")
@app.get("/catalog/series/stvr-az/<path:extras>.json")
def catalog(extras=""):
    params = dict(piece.split("=", 1) for piece in extras.split("&") if "=" in piece)
    letter = params.get("genre", "A").lower()
    if letter not in (list("abcdefghijklmnopqrstuvwxyz") + ["0-9"]):
        return jsonify({"metas": []})
    return jsonify({"metas": listings("9" if letter == "0-9" else letter)})


@app.get("/meta/series/<item_id>.json")
def meta(item_id):
    path = path_from_id(item_id)
    page = BeautifulSoup(fetch(path), "html.parser")
    title = page.select_one("h1") or page.select_one("h2.page__title")
    image = page.select_one('meta[property="og:image"]')
    result = {"id": item_id, "type": "series", "name": title.get_text(" ", strip=True) if title else "STVR relácia", "videos": episodes(path)}
    if image and image.get("content"):
        result["poster"] = urljoin(BASE, image["content"])
    return jsonify({"meta": result})


@app.get("/stream/series/<video_id>.json")
def stream(video_id):
    if not re.fullmatch(r"stvrvideo:\d+", video_id):
        return jsonify({"streams": []})
    clip_id = video_id.split(":", 1)[1]
    data = fetch(f"/json/archive5f.json?id={clip_id}", as_json=True)
    sources = (data.get("clip") or {}).get("sources") or []
    streams = []
    for source in sources:
        url = source.get("src", "")
        if url.startswith("https://") and ".m3u8" in url:
            streams.append({"name": "STVR HLS", "title": "STVR archív", "url": url})
    return jsonify({"streams": streams})


@app.errorhandler(Exception)
def error(exc):
    app.logger.exception("Request failed")
    return jsonify({"error": str(exc)}), 502


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "7000")))
