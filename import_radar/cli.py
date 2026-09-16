"""CLI ImportRadar.

Tryby:
  scan  - zbuduj ranking marzy netto dla ofert DE vs ceny PL
  calc  - policz oplacalnosc jednego auta
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .calculator import CostInputs, compute_margin
from .parser import (
    load_offers_json,
    load_offers_csv,
    load_pl_prices_json,
    Offer,
)
from .radar import build_ranking
from .report import build_markdown, markdown_to_html, render_pdf
from .scraper import scrape_autoscout24

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DE = DATA_DIR / "sample_de_offers.json"
DEFAULT_PL = DATA_DIR / "sample_pl_prices.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="import-radar",
        description="Radar oplacalnosci importu aut DE/NL -> PL (FluxLab).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="Ranking marzy netto dla wielu ofert.")
    p_scan.add_argument(
        "--de", help="Plik ofert DE (JSON lub CSV). Domyslnie: przykladowy dataset."
    )
    p_scan.add_argument(
        "--pl", help="Plik cen PL (JSON). Domyslnie: przykladowy dataset."
    )
    p_scan.add_argument(
        "--eur", type=float, default=4.30, help="Kurs EUR/PLN (domyslnie 4.30)."
    )
    p_scan.add_argument(
        "--top", type=int, default=10, help="Ile pozycji w rankingu (domyslnie 10)."
    )
    p_scan.add_argument(
        "--transport", type=float, help="Nadpisz koszt transportu (PLN)."
    )
    p_scan.add_argument(
        "--live",
        nargs=2,
        metavar=("MAKE", "MODEL"),
        help="Sprobuj scrapowac autoscout24 dla marki/modelu (fallback do pliku).",
    )
    p_scan.add_argument("--md", help="Zapisz raport Markdown do pliku.")
    p_scan.add_argument(
        "--pdf", help="Zapisz raport PDF do pliku (przez google-chrome-stable)."
    )
    p_scan.add_argument("--json-out", help="Zapisz ranking jako JSON.")

    p_calc = sub.add_parser("calc", help="Oplacalnosc jednego auta.")
    p_calc.add_argument(
        "--price-eur", type=float, required=True, help="Cena auta w DE (EUR)."
    )
    p_calc.add_argument(
        "--pl-price", type=float, required=True, help="Szac. cena sprzedazy w PL (PLN)."
    )
    p_calc.add_argument(
        "--cc", type=int, required=True, help="Pojemnosc silnika (cm3)."
    )
    p_calc.add_argument(
        "--eur", type=float, default=4.30, help="Kurs EUR/PLN (domyslnie 4.30)."
    )
    p_calc.add_argument(
        "--electric", action="store_true", help="Auto elektryczne (BEV, akcyza 0)."
    )
    p_calc.add_argument(
        "--class",
        dest="vclass",
        help="Klasa auta dla bufora usterek (np. premium_mid).",
    )
    p_calc.add_argument(
        "--transport", type=float, help="Nadpisz koszt transportu (PLN)."
    )
    p_calc.add_argument("--json-out", help="Zapisz wynik jako JSON.")

    args = parser.parse_args(argv)

    if args.cmd == "scan":
        return _cmd_scan(args)
    if args.cmd == "calc":
        return _cmd_calc(args)
    return 1


def _load_offers(path: Path) -> list[Offer]:
    if path.suffix.lower() == ".csv":
        return load_offers_csv(path)
    return load_offers_json(path)


def _cmd_scan(args) -> int:
    is_sample = False
    offers: list[Offer] = []

    if args.live:
        make, model = args.live
        print(
            f"[scan] Proba scrapowania autoscout24: {make} {model} ...", file=sys.stderr
        )
        offers = scrape_autoscout24(make, model)
        if not offers:
            print(
                "[scan] Scrape nieudany lub zablokowany. Fallback do danych z pliku.",
                file=sys.stderr,
            )

    de_path = Path(args.de) if args.de else DEFAULT_DE
    pl_path = Path(args.pl) if args.pl else DEFAULT_PL
    if not args.de and not args.live:
        is_sample = True
    if not offers:
        offers = _load_offers(de_path)
        if de_path == DEFAULT_DE:
            is_sample = True

    pl_prices = load_pl_prices_json(pl_path)
    if pl_path == DEFAULT_PL:
        is_sample = True

    overrides = {}
    if args.transport is not None:
        overrides["transport_pln"] = args.transport

    deals = build_ranking(offers, pl_prices, args.eur, overrides=overrides)
    if not deals:
        print(
            "Brak dopasowanych ofert (sprawdz zgodnosc make|model|year miedzy DE i PL).",
            file=sys.stderr,
        )
        return 2

    md = build_markdown(deals, top=args.top, is_sample=is_sample, eur_pln=args.eur)

    if args.json_out:
        payload = [
            {"offer": d.offer.to_dict(), "result": d.result.to_dict()}
            for d in deals[: args.top]
        ]
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
        print(f"Zapisano Markdown: {args.md}", file=sys.stderr)

    if args.pdf:
        html = markdown_to_html(md)
        ok = render_pdf(html, args.pdf)
        if ok:
            print(f"Zapisano PDF: {args.pdf}", file=sys.stderr)
        else:
            print(
                "Nie udalo sie wygenerowac PDF (google-chrome-stable).", file=sys.stderr
            )

    if not (args.md or args.pdf or args.json_out):
        print(md)
    else:
        # krotkie podsumowanie na stdout
        for i, d in enumerate(deals[: args.top], 1):
            print(
                f"{i:2}. {d.offer.label:32} marza netto: {d.result.net_margin_pln:>10,.0f} zl "
                f"({d.result.margin_pct:.1f}%)"
            )
    return 0


def _cmd_calc(args) -> int:
    inp = CostInputs(
        de_price_eur=args.price_eur,
        eur_pln=args.eur,
        engine_cc=args.cc,
        is_electric=args.electric,
        vehicle_class=args.vclass,
        transport_pln=args.transport,
    )
    res = compute_margin(inp, args.pl_price)
    b = res.breakdown

    def pln(v):
        return f"{v:,.0f} zl".replace(",", " ")

    print("=== ImportRadar, oplacalnosc jednego auta ===")
    print(f"Cena auta (DE, w PLN):     {pln(b.car_value_pln)}")
    print(f"Akcyza ({b.excise_rate_used * 100:.1f}%):          {pln(b.excise_pln)}")
    print(f"Transport:                 {pln(b.transport_pln)}")
    print(f"Tlumaczenie:               {pln(b.translation_pln)}")
    print(f"Rejestracja:               {pln(b.registration_pln)}")
    print(f"Badanie techniczne:        {pln(b.inspection_pln)}")
    print(f"Ubezpieczenie w drodze:    {pln(b.transit_insurance_pln)}")
    print(f"Bufor na usterki:          {pln(b.defect_buffer_pln)}")
    print(f"---")
    print(f"PELNY KOSZT SPROWADZENIA:   {pln(b.total_landed_cost_pln)}")
    print(f"Szac. cena sprzedazy PL:    {pln(res.pl_market_price_pln)}")
    print(
        f"MARZA NETTO:                {pln(res.net_margin_pln)}  ({res.margin_pct:.1f}%)"
    )

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(res.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Zapisano JSON: {args.json_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
