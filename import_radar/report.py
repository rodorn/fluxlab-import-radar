"""Generowanie raportu: Markdown + HTML, oraz PDF przez google-chrome-stable."""

from __future__ import annotations

import subprocess
import shutil
from datetime import date
from pathlib import Path

from .radar import RankedDeal

CHROME_BIN = "/usr/bin/google-chrome-stable"

# Uwaga: BEZ dlugich myslnikow. Zamiast em-dash uzywamy przecinka.


def _fmt_pln(v: float) -> str:
    return f"{v:,.0f} zl".replace(",", " ")


def _fmt_eur(v: float) -> str:
    return f"{v:,.0f} EUR".replace(",", " ")


def build_markdown(
    deals: list[RankedDeal], top: int, is_sample: bool, eur_pln: float
) -> str:
    lines: list[str] = []
    lines.append("# ImportRadar, Top aut do sprowadzenia z DE/NL")
    lines.append("")
    lines.append(
        f"Data raportu: {date.today().isoformat()}  |  Kurs EUR/PLN: {eur_pln:.2f}"
    )
    lines.append("")
    if is_sample:
        lines.append(
            "> PRZYKLAD, dane demonstracyjne. To nie jest odczyt rynku live. "
            "Ceny DE i PL pochodza z dolaczonego przykladowego datasetu."
        )
        lines.append("")
    lines.append(
        "Marza netto = szacowana cena sprzedazy w PL minus pelny koszt sprowadzenia "
        "(cena auta, akcyza, transport, tlumaczenie, rejestracja, badanie, bufor na usterki)."
    )
    lines.append("")

    ranked = deals[:top]
    lines.append(
        "| # | Auto | Rok | Poj. cm3 | Cena DE | Szac. cena PL | Koszt sprowadzenia | Marza netto | Marza % |"
    )
    lines.append(
        "|--:|------|----:|---------:|--------:|--------------:|-------------------:|------------:|--------:|"
    )
    for i, d in enumerate(ranked, 1):
        o = d.offer
        r = d.result
        lines.append(
            f"| {i} | {o.label} | {o.year} | {o.engine_cc} | "
            f"{_fmt_eur(o.price_eur)} | {_fmt_pln(r.pl_market_price_pln)} | "
            f"{_fmt_pln(r.breakdown.total_landed_cost_pln)} | "
            f"**{_fmt_pln(r.net_margin_pln)}** | {r.margin_pct:.1f}% |"
        )
    lines.append("")

    lines.append("## Szczegoly kosztow (Top pozycje)")
    lines.append("")
    for i, d in enumerate(ranked, 1):
        o, b = d.offer, d.result.breakdown
        lines.append(f"### {i}. {o.label} ({o.engine_cc} cm3)")
        if o.url:
            lines.append(f"Link DE: {o.url}")
        lines.append("")
        lines.append(f"- Cena auta (DE, w PLN): {_fmt_pln(b.car_value_pln)}")
        lines.append(
            f"- Akcyza ({b.excise_rate_used * 100:.1f}%): {_fmt_pln(b.excise_pln)}"
        )
        lines.append(f"- Transport: {_fmt_pln(b.transport_pln)}")
        lines.append(f"- Tlumaczenie: {_fmt_pln(b.translation_pln)}")
        lines.append(f"- Rejestracja: {_fmt_pln(b.registration_pln)}")
        lines.append(f"- Badanie techniczne: {_fmt_pln(b.inspection_pln)}")
        lines.append(f"- Ubezpieczenie w drodze: {_fmt_pln(b.transit_insurance_pln)}")
        lines.append(f"- Bufor na usterki: {_fmt_pln(b.defect_buffer_pln)}")
        lines.append(
            f"- **Pelny koszt sprowadzenia: {_fmt_pln(b.total_landed_cost_pln)}**"
        )
        lines.append(
            f"- Szac. cena sprzedazy PL: {_fmt_pln(d.result.pl_market_price_pln)}"
        )
        lines.append(
            f"- **Marza netto: {_fmt_pln(d.result.net_margin_pln)} ({d.result.margin_pct:.1f}%)**"
        )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Zastrzezenie: raport ma charakter pogladowy. Marza netto to szacunek, "
        "nie gwarancja. Realne koszty (transport, usterki, czas sprzedazy) i ceny "
        "rynkowe moga sie roznic. Weryfikuj VIN, historie i stan techniczny auta."
    )
    lines.append("")
    lines.append("ImportRadar, FluxLab (fluxlab.pl)")
    return "\n".join(lines)


def markdown_to_html(md: str) -> str:
    """Minimalna konwersja markdown->HTML (tabele + naglowki + listy) bez zaleznosci."""
    html_rows: list[str] = []
    in_table = False
    in_list = False
    for raw in md.split("\n"):
        line = raw.rstrip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells).replace(" ", "")) <= set("-:"):
                continue  # separator wiersz
            if not in_table:
                html_rows.append("<table>")
                in_table = True
            tag = (
                "th"
                if all("**" not in c for c in cells) and _is_header_row(cells)
                else "td"
            )
            row = "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells)
            html_rows.append(f"<tr>{row}</tr>")
            continue
        if in_table:
            html_rows.append("</table>")
            in_table = False
        if line.startswith("### "):
            html_rows.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            html_rows.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            html_rows.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("> "):
            html_rows.append(f"<blockquote>{_inline(line[2:])}</blockquote>")
        elif line.startswith("- "):
            if not in_list:
                html_rows.append("<ul>")
                in_list = True
            html_rows.append(f"<li>{_inline(line[2:])}</li>")
            continue
        elif line == "---":
            html_rows.append("<hr>")
        elif line == "":
            html_rows.append("")
        else:
            html_rows.append(f"<p>{_inline(line)}</p>")
        if in_list and not line.startswith("- "):
            html_rows.insert(len(html_rows) - 1, "</ul>")
            in_list = False
    if in_table:
        html_rows.append("</table>")
    if in_list:
        html_rows.append("</ul>")

    body = "\n".join(html_rows)
    return _HTML_TEMPLATE.format(body=body)


def render_pdf(html: str, out_pdf: str | Path) -> bool:
    """Renderuje HTML do PDF przez google-chrome-stable --headless. Zwraca sukces."""
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    tmp_html = out_pdf.with_suffix(".html")
    tmp_html.write_text(html, encoding="utf-8")
    if not Path(CHROME_BIN).exists():
        return False
    cmd = [
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--print-to-pdf={out_pdf}",
        "--no-pdf-header-footer",
        f"file://{tmp_html.resolve()}",
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=90)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return out_pdf.exists()


def _is_header_row(cells: list[str]) -> bool:
    return any(c in {"#", "Auto", "Rok"} for c in cells)


def _inline(text: str) -> str:
    import re

    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', text)
    return text


_HTML_TEMPLATE = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<title>ImportRadar</title>
<style>
  body {{ font-family: 'DejaVu Sans', Arial, sans-serif; color:#1a1a1a; margin:32px; font-size:12px; }}
  h1 {{ color:#0b6; font-size:22px; }}
  h2 {{ margin-top:24px; border-bottom:2px solid #0b6; padding-bottom:4px; }}
  h3 {{ margin-top:16px; color:#333; }}
  table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:11px; }}
  th, td {{ border:1px solid #ccc; padding:6px 8px; text-align:right; }}
  th {{ background:#0b6; color:#fff; }}
  td:nth-child(2), th:nth-child(2) {{ text-align:left; }}
  blockquote {{ background:#fff7e6; border-left:4px solid #f5a623; padding:8px 12px; color:#7a5b00; }}
  a {{ color:#0645ad; word-break:break-all; }}
  hr {{ border:none; border-top:1px solid #ddd; margin:20px 0; }}
  strong {{ color:#0a5; }}
</style></head><body>
{body}
</body></html>"""
