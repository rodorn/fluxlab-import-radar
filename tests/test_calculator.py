"""Testy kalkulatora importu, to serce narzedzia."""

import pytest

from import_radar.calculator import (
    CostInputs,
    compute_import_cost,
    compute_margin,
    excise_rate,
    excise_amount,
    defect_buffer_for_class,
    DEFAULT_DEFECT_BUFFER_PLN,
    EXCISE_RATE_SMALL,
    EXCISE_RATE_LARGE,
)


class TestExciseRate:
    def test_small_engine_below_threshold(self):
        assert excise_rate(1600) == EXCISE_RATE_SMALL

    def test_engine_exactly_2000_is_small(self):
        # 2000 cm3 wlacznie -> nizsza stawka
        assert excise_rate(2000) == EXCISE_RATE_SMALL

    def test_engine_above_2000_is_large(self):
        assert excise_rate(2001) == EXCISE_RATE_LARGE
        assert excise_rate(2993) == EXCISE_RATE_LARGE

    def test_electric_is_zero(self):
        assert excise_rate(3000, is_electric=True) == 0.0
        assert excise_rate(1400, is_electric=True) == 0.0


class TestExciseAmount:
    def test_small_engine_amount(self):
        # 50000 PLN * 3.1%
        assert excise_amount(50000, 1600) == pytest.approx(1550.0)

    def test_large_engine_amount(self):
        # 50000 PLN * 18.6%
        assert excise_amount(50000, 3000) == pytest.approx(9300.0)

    def test_electric_amount_zero(self):
        assert excise_amount(80000, 0, is_electric=True) == 0.0


class TestDefectBuffer:
    def test_known_class(self):
        assert defect_buffer_for_class("premium_large") == 9000.0

    def test_case_insensitive(self):
        assert defect_buffer_for_class("Premium_Mid") == 6000.0

    def test_unknown_class_default(self):
        assert defect_buffer_for_class("nieznana") == DEFAULT_DEFECT_BUFFER_PLN

    def test_none_default(self):
        assert defect_buffer_for_class(None) == DEFAULT_DEFECT_BUFFER_PLN


class TestComputeImportCost:
    def test_full_breakdown_small_engine(self):
        inp = CostInputs(
            de_price_eur=10000,
            eur_pln=4.30,
            engine_cc=1600,
            vehicle_class="compact",
        )
        bd = compute_import_cost(inp)
        assert bd.car_value_pln == pytest.approx(43000.0)
        # akcyza 3.1% z 43000
        assert bd.excise_pln == pytest.approx(1333.0)
        assert bd.excise_rate_used == EXCISE_RATE_SMALL
        # fees = akcyza + vat(0) + transport 3000 + tlum 250 + rej 256
        #        + insp 100 + transit 150 + broker 0 + buffer 2500
        expected_fees = 1333.0 + 3000 + 250 + 256 + 100 + 150 + 2500
        assert bd.fees_total_pln == pytest.approx(expected_fees)
        assert bd.total_landed_cost_pln == pytest.approx(43000.0 + expected_fees)

    def test_large_engine_excise_hits_hard(self):
        small = compute_import_cost(
            CostInputs(20000, 4.30, 1998, vehicle_class="premium_mid")
        )
        large = compute_import_cost(
            CostInputs(20000, 4.30, 2500, vehicle_class="premium_mid")
        )
        # ta sama cena, wieksza pojemnosc -> znacznie wyzsza akcyza
        assert large.excise_pln > small.excise_pln
        diff = large.excise_pln - small.excise_pln
        car_value = 20000 * 4.30
        assert diff == pytest.approx(
            car_value * (EXCISE_RATE_LARGE - EXCISE_RATE_SMALL), rel=1e-3
        )

    def test_overrides_applied(self):
        inp = CostInputs(
            de_price_eur=10000,
            eur_pln=4.0,
            engine_cc=1600,
            transport_pln=1500,
            translation_pln=0,
            registration_pln=0,
            inspection_pln=0,
            transit_insurance_pln=0,
            defect_buffer_pln=0,
        )
        bd = compute_import_cost(inp)
        # tylko akcyza + transport
        assert bd.transport_pln == 1500
        assert bd.fees_total_pln == pytest.approx(bd.excise_pln + 1500)

    def test_electric_no_excise(self):
        bd = compute_import_cost(
            CostInputs(24000, 4.30, 0, is_electric=True, vehicle_class="ev")
        )
        assert bd.excise_pln == 0.0

    def test_vat_optional(self):
        bd = compute_import_cost(CostInputs(10000, 4.0, 1600, vat_rate=0.23))
        assert bd.vat_pln == pytest.approx(40000 * 0.23)


class TestComputeMargin:
    def test_positive_margin(self):
        inp = CostInputs(13500, 4.30, 1498, vehicle_class="compact")
        res = compute_margin(inp, pl_market_price_pln=72000)
        assert res.net_margin_pln == pytest.approx(
            72000 - res.breakdown.total_landed_cost_pln
        )
        assert res.net_margin_pln > 0
        assert res.margin_pct == pytest.approx(
            res.net_margin_pln / res.breakdown.total_landed_cost_pln * 100, rel=1e-3
        )

    def test_negative_margin_big_diesel(self):
        # duzy diesel z wysoka akcyza moze byc nieoplacalny
        inp = CostInputs(19500, 4.30, 2993, vehicle_class="premium_large")
        res = compute_margin(inp, pl_market_price_pln=106000)
        # nie zakladamy znaku, ale marza musi byc spojna z rozbiciem
        assert res.net_margin_pln == pytest.approx(
            106000 - res.breakdown.total_landed_cost_pln
        )

    def test_margin_pct_zero_when_cost_zero(self):
        inp = CostInputs(
            0,
            4.30,
            1600,
            transport_pln=0,
            translation_pln=0,
            registration_pln=0,
            inspection_pln=0,
            transit_insurance_pln=0,
            defect_buffer_pln=0,
        )
        res = compute_margin(inp, 0)
        assert res.margin_pct == 0.0
