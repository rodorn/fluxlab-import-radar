"""Radar oplacalnosci: laczy oferty DE, ceny PL i kalkulator w ranking marzy."""

from __future__ import annotations

from dataclasses import dataclass

from .calculator import CostInputs, MarginResult, compute_margin
from .parser import Offer, pl_price_for


@dataclass
class RankedDeal:
    offer: Offer
    result: MarginResult

    @property
    def net_margin(self) -> float:
        return self.result.net_margin_pln


def build_ranking(
    offers: list[Offer],
    pl_prices: dict[str, float],
    eur_pln: float,
    overrides: dict | None = None,
) -> list[RankedDeal]:
    """Liczy marze netto dla kazdej oferty majacej cene porownawcza w PL,
    zwraca liste posortowana malejaco po marzy netto.

    overrides: opcjonalne nadpisania pozycji kosztowych (np. transport_pln).
    """
    overrides = overrides or {}
    deals: list[RankedDeal] = []
    for offer in offers:
        pl_price = pl_price_for(offer, pl_prices)
        if pl_price is None:
            continue
        inp = CostInputs(
            de_price_eur=offer.price_eur,
            eur_pln=eur_pln,
            engine_cc=offer.engine_cc,
            is_electric=offer.is_electric,
            vehicle_class=offer.vehicle_class,
            **overrides,
        )
        result = compute_margin(inp, pl_price)
        deals.append(RankedDeal(offer=offer, result=result))

    deals.sort(key=lambda d: d.net_margin, reverse=True)
    return deals
