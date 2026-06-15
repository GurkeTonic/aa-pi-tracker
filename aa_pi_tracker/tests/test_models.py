# Django
from django.test import TestCase

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

# AA PI Tracker
from aa_pi_tracker.models import (
    General,
    PiExtractorPin,
    PiOwner,
    PiPlanet,
)


class TestGeneral(TestCase):
    def test_basic_access_permission_exists(self):
        perms = {p[0] for p in General._meta.permissions}
        self.assertIn("view_pi", perms)


class TestPiOwner(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user("testuser")
        AuthUtils.add_main_character(
            cls.user, "Test Char", 12345678, 98000001, "Test Corp", "TST"
        )
        cls.char = EveCharacter.objects.get(character_id=12345678)
        cls.owner = PiOwner.objects.create(user=cls.user, character=cls.char)

    def test_str(self):
        self.assertEqual(str(self.owner), "Test Char")


class TestPiPlanet(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = AuthUtils.create_user("testuser2")
        AuthUtils.add_main_character(
            cls.user, "Test Char 2", 12345679, 98000001, "Test Corp", "TST"
        )
        cls.char = EveCharacter.objects.get(character_id=12345679)
        cls.owner = PiOwner.objects.create(user=cls.user, character=cls.char)
        cls.planet = PiPlanet.objects.create(
            owner=cls.owner,
            planet_id=40000001,
            planet_name="Jita IV",
            planet_type="temperate",
        )

    def test_str(self):
        self.assertIn("Test Char 2", str(self.planet))
        self.assertIn("Jita IV", str(self.planet))

    def test_unique_together(self):
        # Django
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            PiPlanet.objects.create(
                owner=self.owner,
                planet_id=40000001,
                planet_name="Duplicate",
            )


class TestPiExtractorPin(TestCase):
    def test_qty_per_hour_normal(self):
        pin = PiExtractorPin(cycle_time=1800, qty_per_cycle=100)
        self.assertAlmostEqual(pin.qty_per_hour, 200.0)

    def test_qty_per_hour_zero_cycle(self):
        pin = PiExtractorPin(cycle_time=0, qty_per_cycle=100)
        self.assertEqual(pin.qty_per_hour, 0.0)
