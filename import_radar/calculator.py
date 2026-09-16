"""Kalkulator pelnego kosztu sprowadzenia auta z DE/NL do PL.

To jest serce narzedzia. Kazda pozycja kosztowa jest jawna i policzalna.
Wszystkie kwoty w PLN, chyba ze pole ma sufiks _eur.

Zalozenia (stan prawny 2025/2026, rynek uzywanych aut osobowych z UE):
- Zakup uzywanego auta wewnatrz UE (DE/NL -> PL) przez osobe/handlarza:
  co do zasady NIE placi sie ceł ani VAT importowego (to rynek wewnetrzny UE).
  Domyslnie VAT = 0. Handlarz na VAT-marza tez nie dolicza VAT do kosztu nabycia.
- Akcyza od samochodu osobowego: 3,1 proc. dla pojemnosci <= 2000 cm3,
  18,6 proc. powyzej 2000 cm3. Podstawa = wartosc auta (cena zakupu w PLN).
- BEV (auto w pelni elektryczne) sa zwolnione z akcyzy.
- Do tego dochodza realne oplaty okolorejestracyjne i logistyka.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

# Stawki akcyzy wg pojemnosci silnika
EXCISE_RATE_SMALL = 0.031  # <= 2000 cm3
EXCISE_RATE_LARGE = 0.186  # > 2000 cm3
EXCISE_CC_THRESHOLD = 2000

# Domyslne oplaty okolorejestracyjne w PLN (mozna nadpisac)
DEFAULT_TRANSPORT_PLN = 3000.0  # laweta/transport DE->PL, typ. 2000-4000
DEFAULT_TRANSLATION_PLN = 250.0  # tlumaczenie przysiegle dokumentow
DEFAULT_REGISTRATION_PLN = 256.0  # oplata rejestracyjna (tablice, dowod, itd.)
DEFAULT_INSPECTION_PLN = 100.0  # badanie techniczne
DEFAULT_TRANSIT_INSURANCE_PLN = 150.0  # ubezpieczenie w drodze / zielona karta
DEFAULT_BROKER_FEE_PLN = 0.0  # prowizja posrednika po stronie DE (opcjonalnie)


# Bufor na usterki wg klasy/marki auta (PLN). Realistyczne, konserwatywne.
# Klucze to uproszczone segmenty ryzyka serwisowego.
DEFECT_BUFFER_BY_CLASS = {
    "budget": 1500.0,  # male, tanie auta (Fabia, Polo, Corsa)
    "compact": 2500.0,  # kompakty (Golf, Astra, Focus)
    "premium_compact": 4000.0,  # premium kompakt (A3, 1er, A-klasa)
    "premium_mid": 6000.0,  # premium klasa srednia (A4, 3er, C-klasa)
    "premium_large": 9000.0,  # premium klasa wyzsza (A6/A8, 5er/7er, E/S)
    "suv_premium": 8000.0,  # premium SUV (X3/X5, Q5/Q7, GLC/GLE)
    "ev": 3000.0,  # elektryki (male czesci eksploatacyjne, ryzyko baterii osobno)
}
DEFAULT_DEFECT_BUFFER_PLN = 3000.0


def excise_rate(engine_cc: int, is_electric: bool = False) -> float:
    """Zwraca stawke akcyzy dla danej pojemnosci silnika.

    BEV zwolnione (0.0). Reszta: 3,1 proc. do 2000 cm3 wlacznie, 18,6 proc. powyzej.
    """
    if is_electric:
        return 0.0
    if engine_cc <= EXCISE_CC_THRESHOLD:
        return EXCISE_RATE_SMALL
    return EXCISE_RATE_LARGE


def excise_amount(
    car_value_pln: float, engine_cc: int, is_electric: bool = False
) -> float:
    """Kwota akcyzy = wartosc auta * stawka."""
    return round(car_value_pln * excise_rate(engine_cc, is_electric), 2)


def defect_buffer_for_class(vehicle_class: str | None) -> float:
    """Bufor na usterki wg klasy auta. Nieznana klasa -> wartosc domyslna."""
    if vehicle_class is None:
        return DEFAULT_DEFECT_BUFFER_PLN
    return DEFECT_BUFFER_BY_CLASS.get(vehicle_class.lower(), DEFAULT_DEFECT_BUFFER_PLN)


@dataclass
class CostInputs:
    """Wejscie kalkulatora dla jednego auta."""

    de_price_eur: float  # cena auta w DE w EUR
    eur_pln: float  # kurs EUR/PLN
    engine_cc: int  # pojemnosc silnika w cm3
    is_electric: bool = False
    vehicle_class: str | None = None  # patrz DEFECT_BUFFER_BY_CLASS

    # Nadpisywalne pozycje kosztowe (None => wartosc domyslna)
    transport_pln: float | None = None
    translation_pln: float | None = None
    registration_pln: float | None = None
    inspection_pln: float | None = None
    transit_insurance_pln: float | None = None
    broker_fee_pln: float | None = None
    defect_buffer_pln: float | None = None  # None => wg vehicle_class

    # VAT (domyslnie 0 dla nabycia wewnatrzwspolnotowego uzywanego auta)
    vat_rate: float = 0.0


@dataclass
class CostBreakdown:
    """Wynik: pelny rozbicie kosztu sprowadzenia."""

    car_value_pln: float
    excise_pln: float
    excise_rate_used: float
    vat_pln: float
    transport_pln: float
    translation_pln: float
    registration_pln: float
    inspection_pln: float
    transit_insurance_pln: float
    broker_fee_pln: float
    defect_buffer_pln: float
    total_landed_cost_pln: float  # pelny koszt = cena + wszystkie pozycje
    fees_total_pln: float  # suma samych oplat/kosztow (bez ceny auta)

    def to_dict(self) -> dict:
        return asdict(self)


def compute_import_cost(inp: CostInputs) -> CostBreakdown:
    """Liczy pelny koszt sprowadzenia auta (landed cost) z rozbiciem na pozycje."""
    car_value = round(inp.de_price_eur * inp.eur_pln, 2)

    excise = excise_amount(car_value, inp.engine_cc, inp.is_electric)
    rate = excise_rate(inp.engine_cc, inp.is_electric)
    vat = round(car_value * inp.vat_rate, 2)

    transport = _or_default(inp.transport_pln, DEFAULT_TRANSPORT_PLN)
    translation = _or_default(inp.translation_pln, DEFAULT_TRANSLATION_PLN)
    registration = _or_default(inp.registration_pln, DEFAULT_REGISTRATION_PLN)
    inspection = _or_default(inp.inspection_pln, DEFAULT_INSPECTION_PLN)
    transit = _or_default(inp.transit_insurance_pln, DEFAULT_TRANSIT_INSURANCE_PLN)
    broker = _or_default(inp.broker_fee_pln, DEFAULT_BROKER_FEE_PLN)
    if inp.defect_buffer_pln is not None:
        defect = inp.defect_buffer_pln
    else:
        defect = defect_buffer_for_class(inp.vehicle_class)

    fees_total = round(
        excise
        + vat
        + transport
        + translation
        + registration
        + inspection
        + transit
        + broker
        + defect,
        2,
    )
    total = round(car_value + fees_total, 2)

    return CostBreakdown(
        car_value_pln=car_value,
        excise_pln=excise,
        excise_rate_used=rate,
        vat_pln=vat,
        transport_pln=transport,
        translation_pln=translation,
        registration_pln=registration,
        inspection_pln=inspection,
        transit_insurance_pln=transit,
        broker_fee_pln=broker,
        defect_buffer_pln=defect,
        total_landed_cost_pln=total,
        fees_total_pln=fees_total,
    )


@dataclass
class MarginResult:
    """Wynik oplacalnosci: koszt sprowadzenia vs cena sprzedazy w PL."""

    breakdown: CostBreakdown
    pl_market_price_pln: float
    net_margin_pln: float  # marza netto = cena PL - pelny koszt
    margin_pct: float  # marza wzgledem kosztu sprowadzenia

    def to_dict(self) -> dict:
        d = self.breakdown.to_dict()
        d.update(
            {
                "pl_market_price_pln": self.pl_market_price_pln,
                "net_margin_pln": self.net_margin_pln,
                "margin_pct": self.margin_pct,
            }
        )
        return d


def compute_margin(inp: CostInputs, pl_market_price_pln: float) -> MarginResult:
    """Liczy marze netto: cena sprzedazy PL minus pelny koszt sprowadzenia."""
    bd = compute_import_cost(inp)
    margin = round(pl_market_price_pln - bd.total_landed_cost_pln, 2)
    pct = (
        round(margin / bd.total_landed_cost_pln * 100, 2)
        if bd.total_landed_cost_pln
        else 0.0
    )
    return MarginResult(
        breakdown=bd,
        pl_market_price_pln=pl_market_price_pln,
        net_margin_pln=margin,
        margin_pct=pct,
    )


def _or_default(value: float | None, default: float) -> float:
    return default if value is None else value
