"""Scraper rynku DE (autoscout24 / mobile.de) z solidnym fallbackiem.

Portale niemieckie agresywnie chronia sie przed scrapowaniem (Cloudflare,
render po stronie JS, blokady IP). Ta warstwa PROBUJE pobrac listing przez
requests z naglowkami przegladarki i throttlingiem. Jesli sie nie uda,
zwraca puste dane, a CLI plynnie przechodzi na dane z pliku (JSON/CSV).
"""

from __future__ import annotations

import time
import random

import requests

from .parser import Offer, parse_offers_html

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

AUTOSCOUT24_SEARCH = (
    "https://www.autoscout24.de/lst/{make}/{model}"
    "?sort=price&desc=0&size=20&page=1&cy=D&atype=C"
)


def fetch_html(url: str, throttle: float = 2.0, timeout: int = 15) -> str | None:
    """Pobiera HTML z throttlingiem. Zwraca None przy blokadzie/bledzie."""
    time.sleep(throttle + random.uniform(0, 1.0))
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    if _looks_blocked(resp.text):
        return None
    return resp.text


def scrape_autoscout24(make: str, model: str, throttle: float = 2.0) -> list[Offer]:
    """Probuje pobrac oferty z autoscout24. Pusta lista = blokada/brak parsowania."""
    url = AUTOSCOUT24_SEARCH.format(make=make.lower(), model=model.lower())
    html = fetch_html(url, throttle=throttle)
    if not html:
        return []
    return parse_offers_html(html, source="autoscout24")


def _looks_blocked(html: str) -> bool:
    lowered = html.lower()
    markers = [
        "captcha",
        "are you a human",
        "cf-browser-verification",
        "access denied",
        "just a moment",
    ]
    return any(m in lowered for m in markers)
