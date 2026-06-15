"""
Extended model tests covering properties and relationships not tested in test_models.py.
"""

# Django
from django.test import TestCase

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

# AA PI Tracker
from aa_pi_tracker.models import (
    PiExtractorPin,
    PiMarketPrice,
    PiOwner,
    PiPlanet,
    PiProject,
    PiProjectObjective,
    PiProjectPlanet,
    PiStorageItem,
)


def _make_owner(username, char_name, char_id):
    user = AuthUtils.create_user(username)
    AuthUtils.add_main_character(user, char_name, char_id, 98000001, "Test Corp", "TST")
    char = EveCharacter.objects.get(character_id=char_id)
    owner = PiOwner.objects.create(user=user, character=char)
    return user, owner


class TestPiOwnerMaxPlanets(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("owner_test", "Owner Char", 10000001)

    def test_max_planets_none_when_ic_none(self):
        self.owner.interplanetary_consolidation = None
        self.assertIsNone(self.owner.max_planets)

    def test_max_planets_level_0(self):
        self.owner.interplanetary_consolidation = 0
        self.assertEqual(self.owner.max_planets, 1)

    def test_max_planets_level_5(self):
        self.owner.interplanetary_consolidation = 5
        self.assertEqual(self.owner.max_planets, 6)

    def test_max_planets_level_3(self):
        self.owner.interplanetary_consolidation = 3
        self.assertEqual(self.owner.max_planets, 4)


class TestPiPlanetProperties(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("planet_test", "Planet Char", 10000002)
        cls.planet = PiPlanet.objects.create(
            owner=cls.owner,
            planet_id=40000100,
            planet_name="Test IV",
            planet_type="temperate",
        )

    def test_sec_class_highsec(self):
        self.planet.security_status = 0.9
        self.assertEqual(self.planet.sec_class, "success")

    def test_sec_class_lowsec(self):
        self.planet.security_status = 0.3
        self.assertEqual(self.planet.sec_class, "warning")

    def test_sec_class_nullsec(self):
        self.planet.security_status = -0.5
        self.assertEqual(self.planet.sec_class, "danger")

    def test_sec_class_none(self):
        self.planet.security_status = None
        self.assertEqual(self.planet.sec_class, "secondary")

    def test_sec_class_boundary_lowsec(self):
        # 0.45 is the exact boundary → should be "success"
        self.planet.security_status = 0.45
        self.assertEqual(self.planet.sec_class, "success")

    def test_sec_class_boundary_zero(self):
        # 0.0 is still >= 0.0 → "warning"
        self.planet.security_status = 0.0
        self.assertEqual(self.planet.sec_class, "warning")

    def test_sec_display_shows_one_decimal(self):
        self.planet.security_status = 0.9
        self.assertEqual(self.planet.sec_display, "0.9")

    def test_sec_display_none_returns_questionmark(self):
        self.planet.security_status = None
        self.assertEqual(self.planet.sec_display, "?")


class TestPiProjectStr(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, _ = _make_owner("proj_test", "Proj Char", 10000003)
        cls.project = PiProject.objects.create(user=cls.user, name="My PI Project")

    def test_str(self):
        self.assertEqual(str(self.project), "My PI Project")


class TestPiProjectObjectiveStr(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, _ = _make_owner("obj_test", "Obj Char", 10000004)
        cls.project = PiProject.objects.create(user=cls.user, name="Obj Project")
        cls.objective = PiProjectObjective.objects.create(
            project=cls.project,
            schematic_name="Bacteria",
            target_qty_per_hour=3,
        )

    def test_str(self):
        self.assertEqual(str(self.objective), "Bacteria @ 3/h")


class TestPiProjectObjectiveUniqueConstraint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, _ = _make_owner("uniq_test", "Uniq Char", 10000005)
        cls.project = PiProject.objects.create(user=cls.user, name="Uniq Project")
        PiProjectObjective.objects.create(
            project=cls.project, schematic_name="Water", target_qty_per_hour=1
        )

    def test_duplicate_schematic_raises(self):
        # Django
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            PiProjectObjective.objects.create(
                project=self.project, schematic_name="Water", target_qty_per_hour=2
            )


class TestPiStorageItemStr(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("storage_test", "Storage Char", 10000006)
        cls.planet = PiPlanet.objects.create(
            owner=cls.owner,
            planet_id=40000200,
            planet_name="Storage IV",
            planet_type="barren",
        )
        cls.item = PiStorageItem.objects.create(
            planet=cls.planet, type_id=2267, type_name="Base Metals", amount=5000
        )

    def test_str_contains_planet_and_product(self):
        s = str(self.item)
        self.assertIn("Base Metals", s)
        self.assertIn("5,000", s)


class TestPiStorageItemUnique(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("stor_uniq", "Stor Char", 10000007)
        cls.planet = PiPlanet.objects.create(
            owner=cls.owner,
            planet_id=40000201,
            planet_name="Store V",
            planet_type="ice",
        )
        PiStorageItem.objects.create(
            planet=cls.planet, type_id=2267, type_name="Base Metals", amount=100
        )

    def test_duplicate_type_id_raises(self):
        # Django
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            PiStorageItem.objects.create(
                planet=self.planet, type_id=2267, type_name="Base Metals", amount=200
            )


class TestPiMarketPriceStr(TestCase):
    def test_str_shows_isk_formatted(self):
        price = PiMarketPrice(
            type_id=2267, type_name="Base Metals", tier=0, jita_buy=1234567.0
        )
        s = str(price)
        self.assertIn("Base Metals", s)
        self.assertIn("ISK", s)


class TestPiProjectPlanetDuplicateAllowed(TestCase):
    """Migration 0010 removed unique_together — same planet can appear multiple times in a project."""

    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("pp_uniq", "PP Char", 10000008)
        cls.planet = PiPlanet.objects.create(
            owner=cls.owner, planet_id=40000300, planet_name="PP IV", planet_type="gas"
        )
        cls.project = PiProject.objects.create(user=cls.user, name="PP Project")
        PiProjectPlanet.objects.create(project=cls.project, planet=cls.planet)

    def test_duplicate_project_planet_allowed(self):
        PiProjectPlanet.objects.create(project=self.project, planet=self.planet)
        self.assertEqual(
            PiProjectPlanet.objects.filter(
                project=self.project, planet=self.planet
            ).count(),
            2,
        )


class TestPiExtractorPinQtyPerHour(TestCase):
    """Additional edge cases beyond test_models.py."""

    def test_one_hour_cycle(self):
        pin = PiExtractorPin(cycle_time=3600, qty_per_cycle=500)
        self.assertAlmostEqual(pin.qty_per_hour, 500.0)

    def test_negative_cycle_time_returns_zero(self):
        pin = PiExtractorPin(cycle_time=-1, qty_per_cycle=100)
        self.assertEqual(pin.qty_per_hour, 0.0)

    def test_zero_qty_per_cycle(self):
        pin = PiExtractorPin(cycle_time=1800, qty_per_cycle=0)
        self.assertAlmostEqual(pin.qty_per_hour, 0.0)
