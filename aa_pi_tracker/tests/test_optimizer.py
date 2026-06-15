"""Optimizer math regression tests.

Guards against the A1 double-rounding bug: scaling already-ceiled 1× factory/
planet counts by qty_per_hour over-estimates the plan. ``production_plan`` must
apply qty *before* rounding (single ceil).
"""

import math

from django.test import SimpleTestCase

from aa_pi_tracker.pi_data import SCHEMATICS, production_plan
from aa_pi_tracker.pi_data.formulas import expand_production, output_per_hour


class ProductionPlanQtyScalingTests(SimpleTestCase):
    QTY = 7

    def _tier2plus(self):
        return [n for n, s in SCHEMATICS.items() if s["tier"] >= 2]

    def test_output_scales_linearly(self):
        for name in self._tier2plus():
            base = production_plan(name, 1)
            scaled = production_plan(name, self.QTY)
            self.assertAlmostEqual(
                scaled["output_per_hour"], base["output_per_hour"] * self.QTY, places=6,
                msg=f"{name}: output_per_hour must scale linearly with qty",
            )

    def test_integer_counts_single_ceil_not_double(self):
        """Scaled integer counts must never exceed qty × the 1× count (which is
        exactly what the old double-ceil produced), and for at least one
        schematic must be strictly smaller — proving rounding happens once."""
        saw_strictly_smaller = False
        for name in self._tier2plus():
            base = production_plan(name, 1)
            scaled = production_plan(name, self.QTY)
            for key in ("total_aifs", "total_miners", "total_planets", "factory_planets"):
                self.assertLessEqual(
                    scaled[key], self.QTY * base[key],
                    msg=f"{name}.{key}: {scaled[key]} > {self.QTY}×{base[key]} — double-rounding regression",
                )
                if scaled[key] < self.QTY * base[key]:
                    saw_strictly_smaller = True
        self.assertTrue(
            saw_strictly_smaller,
            "expected at least one count strictly below qty×1× (rounding once)",
        )

    def test_counts_match_single_ceil_of_scaled_factories(self):
        """total_aifs at qty must equal the ceil of the qty-scaled continuous
        factory counts — recomputed independently from expand_production."""
        for name in self._tier2plus():
            scaled = production_plan(name, self.QTY)
            out_h = output_per_hour(name) * self.QTY
            factories, _ = expand_production([(name, out_h)])
            expected_aifs = sum(
                math.ceil(c) for n, c in factories.items()
                if SCHEMATICS.get(n, {}).get("tier") in (2, 3)
            )
            self.assertEqual(
                scaled["total_aifs"], expected_aifs,
                msg=f"{name}: total_aifs must be single-ceil of scaled factories",
            )

    def test_internal_consistency(self):
        for name in self._tier2plus():
            p = production_plan(name, self.QTY)
            self.assertEqual(p["total_aifs"], sum(p["aifs"].values()))
            self.assertEqual(p["total_planets"], p["total_miners"] + p["factory_planets"])
