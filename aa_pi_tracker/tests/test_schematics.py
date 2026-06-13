"""
Tests for aa_pi_tracker.schematics — pure-Python functions, no DB needed.
"""
import math

from django.test import SimpleTestCase

from aa_pi_tracker.pi_data import (
    PLANET_TYPE_P0,
    PLANET_TYPE_SLUG_TO_P0,
    SCHEMATICS,
    TIER_VOLUMES,
    expand_production,
    get_item_tier,
    get_item_volume,
    output_per_hour,
    production_plan,
    suggest_factory_setup,
)


class TestOutputPerHour(SimpleTestCase):
    def test_p1_factory(self):
        # P1: 20 units / 1800 s cycle = 40 units/h
        self.assertAlmostEqual(output_per_hour("Bacteria"), 40.0)

    def test_p2_factory(self):
        # P2: 5 units / 3600 s cycle = 5 units/h
        self.assertAlmostEqual(output_per_hour("Biocells"), 5.0)

    def test_p3_factory(self):
        # P3: 3 units / 3600 s cycle = 3 units/h
        self.assertAlmostEqual(output_per_hour("Camera Drones"), 3.0)

    def test_p4_factory(self):
        # P4: 1 unit / 3600 s cycle = 1 unit/h
        self.assertAlmostEqual(output_per_hour("Broadcast Node"), 1.0)


class TestGetItemTier(SimpleTestCase):
    def test_p0_resource(self):
        self.assertEqual(get_item_tier("Base Metals"), 0)
        self.assertEqual(get_item_tier("Microorganisms"), 0)

    def test_p1_product(self):
        self.assertEqual(get_item_tier("Bacteria"), 1)
        self.assertEqual(get_item_tier("Water"), 1)

    def test_p2_product(self):
        self.assertEqual(get_item_tier("Biocells"), 2)

    def test_p3_product(self):
        self.assertEqual(get_item_tier("Camera Drones"), 3)

    def test_p4_product(self):
        self.assertEqual(get_item_tier("Broadcast Node"), 4)

    def test_unknown_returns_minus_one(self):
        self.assertEqual(get_item_tier("Tritanium"), -1)
        self.assertEqual(get_item_tier(""), -1)


class TestGetItemVolume(SimpleTestCase):
    def test_p0_volume(self):
        self.assertAlmostEqual(get_item_volume("Base Metals"), TIER_VOLUMES[0])

    def test_p1_volume(self):
        self.assertAlmostEqual(get_item_volume("Bacteria"), TIER_VOLUMES[1])

    def test_p4_volume(self):
        self.assertAlmostEqual(get_item_volume("Broadcast Node"), TIER_VOLUMES[4])

    def test_unknown_item_returns_fallback(self):
        # Unknown items fall back to 1.0 (tier -1 not in TIER_VOLUMES)
        self.assertAlmostEqual(get_item_volume("Tritanium"), 1.0)


class TestExpandProduction(SimpleTestCase):
    def test_p1_only(self):
        factories, extractions = expand_production([("Bacteria", 40.0)])
        # 40 Bacteria/h = 1 factory; needs 6000 Microorganisms/h
        self.assertAlmostEqual(factories["Bacteria"], 1.0)
        self.assertAlmostEqual(extractions["Microorganisms"], 6000.0)

    def test_p2_chain(self):
        # Biocells = 5/h from 1 factory; inputs: 40 Biofuels/h + 40 Precious Metals/h
        factories, extractions = expand_production([("Biocells", 5.0)])
        self.assertAlmostEqual(factories["Biocells"], 1.0)
        self.assertIn("Biofuels", factories)
        self.assertIn("Precious Metals", factories)
        self.assertIn("Carbon Compounds", extractions)
        self.assertIn("Noble Metals", extractions)

    def test_multiple_objectives(self):
        factories, extractions = expand_production([
            ("Bacteria", 40.0),
            ("Water", 40.0),
        ])
        self.assertAlmostEqual(factories["Bacteria"], 1.0)
        self.assertAlmostEqual(factories["Water"], 1.0)
        self.assertIn("Microorganisms", extractions)
        self.assertIn("Aqueous Liquids", extractions)

    def test_empty_objectives(self):
        factories, extractions = expand_production([])
        self.assertEqual(factories, {})
        self.assertEqual(extractions, {})

    def test_p4_chain_returns_p0_extractions(self):
        factories, extractions = expand_production([("Broadcast Node", 1.0)])
        # Should cascade all the way down to P0
        self.assertTrue(len(extractions) > 0)
        for resource in extractions:
            self.assertIn(resource, {
                "Base Metals", "Noble Metals", "Heavy Metals", "Non-CS Crystals",
                "Felsic Magma", "Aqueous Liquids", "Ionic Solutions", "Noble Gas",
                "Reactive Gas", "Suspended Plasma", "Microorganisms", "Planktic Colonies",
                "Complex Organisms", "Carbon Compounds", "Autotrophs",
            })


class TestSuggestFactorySetup(SimpleTestCase):
    def test_no_extractors_returns_empty(self):
        result = suggest_factory_setup({})
        self.assertEqual(result["p1_chains"], [])
        self.assertEqual(result["p2_chains"], [])

    def test_single_p0_produces_p1_chain(self):
        # 12000 Microorganisms/h → 2 P1 Bacteria factories
        result = suggest_factory_setup({"Microorganisms": 12000})
        p1_names = [c["product"] for c in result["p1_chains"]]
        self.assertIn("Bacteria", p1_names)
        bac = next(c for c in result["p1_chains"] if c["product"] == "Bacteria")
        self.assertEqual(bac["optimal_factories"], 2)

    def test_p0_below_threshold_no_chain(self):
        # Less than 6000/h → can't run 1 full factory
        result = suggest_factory_setup({"Microorganisms": 5999})
        self.assertEqual(result["p1_chains"], [])

    def test_two_p0s_suggest_p2_chain(self):
        # Biofuels + Precious Metals → Biocells (P2)
        # Each P1: 6 factories × 6000 P0/h = need 36000 of each
        extraction_rates = {
            "Carbon Compounds": 36000,   # → 6 Biofuels factories = 240 Biofuels/h
            "Noble Metals": 36000,       # → 6 Precious Metals factories = 240 PMs/h
        }
        result = suggest_factory_setup(extraction_rates)
        p2_names = [c["product"] for c in result["p2_chains"]]
        self.assertIn("Biocells", p2_names)

    def test_p1_utilization_correct(self):
        # 9000 P0/h → 1 factory (uses 6000) → utilization = 6000/9000 = 66.7%
        result = suggest_factory_setup({"Microorganisms": 9000})
        bac = next(c for c in result["p1_chains"] if c["product"] == "Bacteria")
        self.assertAlmostEqual(bac["utilization_pct"], 66.7, places=1)


class TestProductionPlan(SimpleTestCase):
    def test_p1_plan(self):
        plan = production_plan("Bacteria")
        self.assertIn("miners_per_p0", plan)
        self.assertIn("Microorganisms", plan["miners_per_p0"])
        self.assertGreater(plan["total_miners"], 0)
        self.assertGreater(plan["output_per_hour"], 0)
        self.assertGreater(plan["output_per_day"], 0)
        # BIFs run on the miner planet itself — no separate factory planet for P1
        self.assertEqual(plan["factory_planets"], 0)
        self.assertEqual(plan["total_planets"], plan["total_miners"])
        # P1 has no AIFs or HTpps
        self.assertEqual(plan["aifs"], {})
        self.assertEqual(plan["htpps"], {})

    def test_p2_plan_has_aifs_no_htpp(self):
        plan = production_plan("Coolant")
        self.assertGreater(len(plan["aifs"]), 0)
        self.assertEqual(plan["htpps"], {})
        # All aifs are tier 2 or 3
        for name in plan["aifs"]:
            self.assertIn(SCHEMATICS[name]["tier"], (2, 3))

    def test_p3_plan_has_aifs_no_htpp(self):
        plan = production_plan("Robotics")
        self.assertGreater(len(plan["aifs"]), 0)
        self.assertEqual(plan["htpps"], {})

    def test_p4_plan_has_htpp(self):
        plan = production_plan("Broadcast Node")
        # Exactly 1 High-Tech Production Plant for the P4 product
        self.assertIn("Broadcast Node", plan["htpps"])
        self.assertEqual(plan["htpps"]["Broadcast Node"], 1)
        # AIFs are tier 2/3 only
        for name in plan["aifs"]:
            self.assertIn(SCHEMATICS[name]["tier"], (2, 3))
        # "Broadcast Node" must NOT appear in aifs (it's a HTPP)
        self.assertNotIn("Broadcast Node", plan["aifs"])
        # factory_planets based on aifs only (not htpps)
        expected = math.ceil(plan["total_aifs"] / 24)
        self.assertEqual(plan["factory_planets"], max(1, expected))

    def test_p4_plan_has_factory_planets(self):
        plan = production_plan("Broadcast Node")
        self.assertGreater(plan["factory_planets"], 0)
        self.assertGreater(plan["total_planets"], plan["total_miners"])

    def test_total_planets_equals_miners_plus_factories(self):
        plan = production_plan("Robotics")
        self.assertEqual(plan["total_planets"], plan["total_miners"] + plan["factory_planets"])

    def test_total_aifs_excludes_htpp(self):
        # For P4 Integrity Response Drones: 42 pure AIFs + 1 HTPP = 43 total buildings
        # total_aifs should be 42 (HTPP not counted)
        plan = production_plan("Integrity Response Drones")
        self.assertEqual(plan["total_aifs"], sum(plan["aifs"].values()))
        self.assertNotEqual(plan["total_aifs"], sum(plan["aifs"].values()) + sum(plan["htpps"].values()))


class TestPlanetTypeP0(SimpleTestCase):
    def test_temperate_has_autotrophs(self):
        # Temperate (type_id 11) should have Autotrophs
        self.assertIn("Autotrophs", PLANET_TYPE_P0[11])

    def test_barren_has_no_autotrophs(self):
        # Barren (type_id 2016) should NOT have Autotrophs
        self.assertNotIn("Autotrophs", PLANET_TYPE_P0[2016])

    def test_slug_mapping_consistent(self):
        # PLANET_TYPE_SLUG_TO_P0 should match PLANET_TYPE_P0 for all standard slugs
        self.assertEqual(PLANET_TYPE_SLUG_TO_P0["temperate"], PLANET_TYPE_P0[11])
        self.assertEqual(PLANET_TYPE_SLUG_TO_P0["ice"], PLANET_TYPE_P0[12])
        self.assertEqual(PLANET_TYPE_SLUG_TO_P0["barren"], PLANET_TYPE_P0[2016])

    def test_all_eight_planet_types_covered(self):
        expected_slugs = {"temperate", "ice", "gas", "oceanic", "lava", "barren", "storm", "plasma"}
        self.assertEqual(set(PLANET_TYPE_SLUG_TO_P0.keys()), expected_slugs)
