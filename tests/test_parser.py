"""Testy parsera ofert i dopasowania cen PL."""

import json

import pytest

from import_radar.parser import (
    Offer,
    load_offers_json,
    load_offers_csv,
    load_pl_prices_json,
    pl_price_for,
    parse_price_eur,
    parse_offers_html,
    _guess_cc,
    _guess_year,
)

SAMPLE_HTML = """
<html><body>
<article>
  <h2>VW Golf 1.5 TSI</h2>
  <span>13.900 EUR</span>
  <div>2019, 2.0 l, 89.000 km</div>
  <a href="https://www.autoscout24.de/angebote/x1">Details</a>
</article>
<article>
  <h2>BMW 320d</h2>
  <span>15.500 EUR</span>
  <div>2018, 1998 ccm</div>
  <a href="https://www.autoscout24.de/angebote/x2">Details</a>
</article>
</body></html>
"""


class TestPriceParsing:
    def test_german_format_with_euro_suffix(self):
        assert parse_price_eur("13.900 EUR") == 13900.0

    def test_euro_prefix(self):
        assert parse_price_eur("Preis: 8.500 EUR inkl.") == 8500.0

    def test_plain_digits(self):
        assert parse_price_eur("12000") == 12000.0

    def test_empty(self):
        assert parse_price_eur("") is None


class TestGuessers:
    def test_guess_year(self):
        assert _guess_year("Baujahr 2019, 89.000 km") == 2019

    def test_guess_cc_from_liters(self):
        assert _guess_cc("2.0 l TDI") == 2000

    def test_guess_cc_from_ccm(self):
        assert _guess_cc("1998 ccm") == 1998

    def test_guess_cc_missing(self):
        assert _guess_cc("brak danych") == 0


class TestHtmlParser:
    def test_parses_articles(self):
        offers = parse_offers_html(SAMPLE_HTML, source="autoscout24")
        assert len(offers) == 2
        golf = offers[0]
        assert golf.make == "VW"
        assert golf.price_eur == 13900.0
        assert golf.year == 2019
        assert golf.url.endswith("x1")

    def test_empty_html_no_crash(self):
        assert parse_offers_html("<html></html>") == []


class TestJsonCsvLoading:
    def test_load_offers_json(self, tmp_path):
        p = tmp_path / "de.json"
        p.write_text(
            json.dumps(
                {
                    "offers": [
                        {
                            "make": "Audi",
                            "model": "A4",
                            "year": 2019,
                            "engine_cc": 1968,
                            "price_eur": 18500,
                            "vehicle_class": "premium_mid",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        offers = load_offers_json(p)
        assert offers[0].make == "Audi"
        assert offers[0].engine_cc == 1968

    def test_load_offers_csv(self, tmp_path):
        p = tmp_path / "de.csv"
        p.write_text(
            "make,model,year,engine_cc,price_eur,is_electric,vehicle_class\n"
            "Tesla,Model3,2020,0,24000,true,ev\n",
            encoding="utf-8",
        )
        offers = load_offers_csv(p)
        assert offers[0].is_electric is True
        assert offers[0].make == "Tesla"

    def test_load_pl_prices_list(self, tmp_path):
        p = tmp_path / "pl.json"
        p.write_text(
            json.dumps(
                {
                    "prices": [
                        {
                            "make": "BMW",
                            "model": "320d",
                            "year": 2018,
                            "price_pln": 86000,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        prices = load_pl_prices_json(p)
        assert prices["bmw|320d|2018"] == 86000.0


class TestPlMatching:
    def test_exact_match(self):
        prices = {"bmw|320d|2018": 86000.0}
        offer = Offer("BMW", "320d", 2018, 1995, 15900)
        assert pl_price_for(offer, prices) == 86000.0

    def test_partial_match_without_year(self):
        prices = {"bmw|320d|2017": 80000.0}
        offer = Offer("BMW", "320d", 2018, 1995, 15900)
        assert pl_price_for(offer, prices) == 80000.0

    def test_no_match_returns_none(self):
        prices = {"audi|a4|2019": 101000.0}
        offer = Offer("BMW", "320d", 2018, 1995, 15900)
        assert pl_price_for(offer, prices) is None
