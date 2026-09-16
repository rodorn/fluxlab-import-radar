"""Parsowanie ofert aut: z JSON/CSV (fallback) oraz z HTML (scraper DE).

Model oferty jest wspolny dla obu zrodel, dzieki czemu radar liczy
oplacalnosc niezaleznie od tego, skad przyszly dane.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Offer:
    """Pojedyncza oferta auta z rynku DE/NL."""

    make: str
    model: str
    year: int
    engine_cc: int
    price_eur: float
    mileage_km: int = 0
    fuel: str = ""
    is_electric: bool = False
    vehicle_class: str | None = None
    url: str = ""
    source: str = ""  # np. autoscout24, mobile.de, sample
    title: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def label(self) -> str:
        return f"{self.make} {self.model} {self.year}".strip()


def load_offers_json(path: str | Path) -> list[Offer]:
    """Wczytuje liste ofert DE z pliku JSON (lista obiektow)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "offers" in data:
        data = data["offers"]
    return [_offer_from_dict(row) for row in data]


def load_offers_csv(path: str | Path) -> list[Offer]:
    """Wczytuje liste ofert DE z pliku CSV (naglowki = pola Offer)."""
    with Path(path).open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return [_offer_from_dict(row) for row in reader]


def load_pl_prices_json(path: str | Path) -> dict[str, float]:
    """Wczytuje mape porownawczych cen sprzedazy w PL (Otomoto).

    Klucz = 'make|model|year' (male litery), wartosc = mediana ceny PL w PLN.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "prices" in data:
        data = data["prices"]
    out: dict[str, float] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            out[_normalize_key(k)] = float(v)
    else:
        for row in data:
            key = _pl_key(row["make"], row["model"], int(row["year"]))
            out[key] = float(row["price_pln"])
    return out


def pl_price_for(offer: Offer, pl_prices: dict[str, float]) -> float | None:
    """Znajduje porownawcza cene PL dla oferty (dopasowanie po make|model|year)."""
    key = _pl_key(offer.make, offer.model, offer.year)
    if key in pl_prices:
        return pl_prices[key]
    # fallback: dopasowanie bez rocznika (make|model)
    partial = _normalize_key(f"{offer.make}|{offer.model}")
    for k, v in pl_prices.items():
        if k.startswith(partial + "|") or k == partial:
            return v
    return None


# --- Parsowanie HTML (best effort, scraper DE) ---

# Cena: liczba (format niemiecki 13.900 lub 8500) tuz przy € / EUR
_PRICE_RE = re.compile(
    r"(?:€|EUR)\s*(\d{1,3}(?:[.\s]\d{3})+|\d{3,6})"
    r"|(\d{1,3}(?:[.\s]\d{3})+|\d{3,6})\s*(?:€|EUR)",
    re.IGNORECASE,
)
_CC_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:l|ccm|cm3|cm³)\b", re.IGNORECASE)


def parse_price_eur(text: str) -> float | None:
    """Wyciaga cene w EUR z surowego tekstu (formaty niemieckie: 12.900 EUR)."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if m:
        raw = m.group(1) or m.group(2) or ""
        digits = re.sub(r"[^\d]", "", raw)
        return float(digits) if digits else None
    # brak markera waluty: potraktuj caly tekst jako liczbe
    digits = re.sub(r"[^\d]", "", text)
    return float(digits) if digits else None


def parse_offers_html(html: str, source: str = "autoscout24") -> list[Offer]:
    """Best-effort parser listingu HTML. Zwraca liste ofert (moze byc pusta).

    Uklad HTML na mobile.de/autoscout24 czesto sie zmienia i bywa
    renderowany po stronie JS, wiec ta funkcja jest z zalozenia
    tolerancyjna: probuje kilku selektorow i nie wywala sie na brakach.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    offers: list[Offer] = []

    candidates = soup.select(
        "article, [data-testid*='result-item'], .cldt-summary-full-item"
    )
    for node in candidates:
        link = node.find("a", href=True)
        url = link["href"] if link else ""
        title_el = node.find(["h2", "h3"])
        title = (
            title_el.get_text(" ", strip=True)
            if title_el
            else node.get_text(" ", strip=True)[:80]
        )
        price = parse_price_eur(node.get_text(" ", strip=True))
        if not title or price is None:
            continue
        make, model = _split_make_model(title)
        offers.append(
            Offer(
                make=make,
                model=model,
                year=_guess_year(node.get_text(" ", strip=True)),
                engine_cc=_guess_cc(node.get_text(" ", strip=True)),
                price_eur=price,
                url=url,
                source=source,
                title=title,
            )
        )
    return offers


# --- helpers ---


def _offer_from_dict(row: dict) -> Offer:
    def _b(v):
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in {"1", "true", "yes", "tak"}

    return Offer(
        make=str(row["make"]).strip(),
        model=str(row["model"]).strip(),
        year=int(row["year"]),
        engine_cc=int(row.get("engine_cc") or 0),
        price_eur=float(row["price_eur"]),
        mileage_km=int(row.get("mileage_km") or 0),
        fuel=str(row.get("fuel") or "").strip(),
        is_electric=_b(row.get("is_electric", False)),
        vehicle_class=(
            str(row["vehicle_class"]).strip() if row.get("vehicle_class") else None
        ),
        url=str(row.get("url") or "").strip(),
        source=str(row.get("source") or "").strip(),
        title=str(row.get("title") or "").strip(),
    )


def _pl_key(make: str, model: str, year: int) -> str:
    return _normalize_key(f"{make}|{model}|{year}")


def _normalize_key(key: str) -> str:
    return "|".join(part.strip().lower() for part in key.split("|"))


def _split_make_model(title: str) -> tuple[str, str]:
    parts = title.split()
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], parts[1])


def _guess_year(text: str) -> int:
    m = re.search(r"\b(19|20)\d{2}\b", text)
    return int(m.group(0)) if m else 0


def _guess_cc(text: str) -> int:
    m = _CC_RE.search(text)
    if not m:
        return 0
    val = m.group(1).replace(",", ".")
    try:
        liters = float(val)
    except ValueError:
        return 0
    if liters < 10:  # to sa litry, np. 2.0
        return int(round(liters * 1000))
    return int(liters)
