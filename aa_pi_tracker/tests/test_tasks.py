from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.utils import timezone

from allianceauth.eveonline.models import EveCharacter
from allianceauth.notifications.models import Notification
from allianceauth.tests.auth_utils import AuthUtils

from aa_pi_tracker import tasks
from aa_pi_tracker.models import (
    PiExtractorPin,
    PiMaintenanceLog,
    PiOwner,
    PiPlanet,
    PiProject,
    PiProjectPlanet,
)


def _make_owner(name, char_id):
    user = AuthUtils.create_user(name)
    AuthUtils.add_main_character(user, name, char_id, 98000001, "Test Corp", "TST")
    char = EveCharacter.objects.get(character_id=char_id)
    return user, PiOwner.objects.create(user=user, character=char)


class TestCheckExtractorExpiry(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("expiry_user", 90000001)
        cls.planet = PiPlanet.objects.create(
            owner=cls.owner, planet_id=40010001, planet_name="P-1", planet_type="barren"
        )

    def _pin(self, hours, notified=False, product="Water"):
        return PiExtractorPin.objects.create(
            planet=self.planet,
            product_type_id=2268,
            product_name=product,
            cycle_time=3600,
            qty_per_cycle=1000,
            head_count=1,
            expiry_time=timezone.now() + timedelta(hours=hours),
            notified_expiry=notified,
        )

    def test_notifies_soon_expiring_and_flags(self):
        pin = self._pin(hours=2)
        tasks.check_extractor_expiry()
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        pin.refresh_from_db()
        self.assertTrue(pin.notified_expiry)

    def test_dedup_on_second_run(self):
        self._pin(hours=2)
        tasks.check_extractor_expiry()
        tasks.check_extractor_expiry()
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_far_future_not_notified(self):
        self._pin(hours=240)  # well beyond the 24h default window
        tasks.check_extractor_expiry()
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)

    def test_already_notified_is_skipped(self):
        self._pin(hours=2, notified=True)
        tasks.check_extractor_expiry()
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)


class TestSyncPinsFlagPreservation(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("sync_user", 90000002)
        cls.planet = PiPlanet.objects.create(
            owner=cls.owner, planet_id=40010002, planet_name="P-2", planet_type="barren"
        )

    @staticmethod
    def _fake_data(expiry):
        # product_type_id 2268 = Aqueous Liquids (in P0_TYPES) → no SDE lookup needed
        ext = SimpleNamespace(
            product_type_id=2268, cycle_time=3600, qty_per_cycle=1000, heads=[{}]
        )
        pin = SimpleNamespace(
            extractor_details=ext,
            schematic_id=None,
            expiry_time=expiry,
            install_time=None,
            last_cycle_start=None,
            contents=[],
        )
        return SimpleNamespace(pins=[pin])

    @staticmethod
    def _esi_returning(data):
        m = MagicMock()
        (
            m.client.Planetary_Interaction.GetCharactersCharacterIdPlanetsPlanetId
            .return_value.result.return_value
        ) = data
        return m

    def _sync(self, expiry):
        with patch.object(tasks, "esi", self._esi_returning(self._fake_data(expiry))):
            tasks._sync_planet_pins(self.planet, 90000002, token="tok")

    def test_flag_preserved_for_same_program(self):
        expiry = timezone.now() + timedelta(hours=5)
        self._sync(expiry)
        self.assertFalse(self.planet.extractors.get().notified_expiry)
        self.planet.extractors.update(notified_expiry=True)
        self._sync(expiry)  # same expiry → still the same running program
        self.assertTrue(self.planet.extractors.get().notified_expiry)

    def test_flag_reset_for_new_program(self):
        self._sync(timezone.now() + timedelta(hours=5))
        self.planet.extractors.update(notified_expiry=True)
        self._sync(timezone.now() + timedelta(hours=9))  # new expiry → new program
        self.assertFalse(self.planet.extractors.get().notified_expiry)


class TestTryLinkProjectPlanets(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("link_user", 90000010)
        cls.project = PiProject.objects.create(user=cls.user, name="Link Test")

    def _planet(self, planet_id, planet_type, system):
        return PiPlanet.objects.create(
            owner=self.owner,
            planet_id=planet_id,
            planet_type=planet_type,
            solar_system_name=system,
        )

    def _slot(self, planet_type, system, role="miner"):
        return PiProjectPlanet.objects.create(
            project=self.project,
            planet=None,
            role=role,
            planned_char_id=self.owner.character.character_id,
            planned_char_name=self.owner.character.character_name,
            planned_planet_type=planet_type,
            planned_system_name=system,
        )

    def test_links_unambiguous_match(self):
        planet = self._planet(40020001, "barren", "Jita")
        slot = self._slot("barren", "Jita")
        tasks._try_link_project_planets(self.owner)
        slot.refresh_from_db()
        self.assertEqual(slot.planet, planet)

    def test_skips_ambiguous_same_type_and_system(self):
        self._planet(40020002, "barren", "Amarr")
        self._planet(40020003, "barren", "Amarr")
        slot = self._slot("barren", "Amarr")
        tasks._try_link_project_planets(self.owner)
        slot.refresh_from_db()
        self.assertIsNone(slot.planet)

    def test_skips_slot_without_planned_system(self):
        self._planet(40020004, "barren", "Dodixie")
        slot = PiProjectPlanet.objects.create(
            project=self.project, planet=None, role="miner",
            planned_char_id=self.owner.character.character_id,
            planned_planet_type="barren",
            planned_system_name="",
        )
        tasks._try_link_project_planets(self.owner)
        slot.refresh_from_db()
        self.assertIsNone(slot.planet)

    def test_skips_already_linked_planet(self):
        planet = self._planet(40020005, "temperate", "Rens")
        other_project = PiProject.objects.create(user=self.user, name="Other")
        PiProjectPlanet.objects.create(project=other_project, planet=planet)
        slot = self._slot("temperate", "Rens")
        tasks._try_link_project_planets(self.owner)
        slot.refresh_from_db()
        self.assertIsNone(slot.planet)

    def test_no_double_link_when_two_slots_one_planet(self):
        planet = self._planet(40020006, "lava", "Hek")
        slot1 = self._slot("lava", "Hek")
        slot2 = self._slot("lava", "Hek")
        tasks._try_link_project_planets(self.owner)
        slot1.refresh_from_db()
        slot2.refresh_from_db()
        linked = [s for s in (slot1, slot2) if s.planet == planet]
        unlinked = [s for s in (slot1, slot2) if s.planet is None]
        self.assertEqual(len(linked), 1)
        self.assertEqual(len(unlinked), 1)

    def test_no_match_leaves_slot_untouched(self):
        slot = self._slot("oceanic", "Nonexistent")
        tasks._try_link_project_planets(self.owner)
        slot.refresh_from_db()
        self.assertIsNone(slot.planet)


class TestPurgeOldMaintenanceLogs(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user, cls.owner = _make_owner("maint_user", 90000003)
        cls.project = PiProject.objects.create(user=cls.user, name="Proj")

    def test_purges_old_keeps_recent(self):
        today = timezone.localdate()
        old = PiMaintenanceLog.objects.create(
            project=self.project, character_id=90000003, date=today - timedelta(days=100)
        )
        recent = PiMaintenanceLog.objects.create(
            project=self.project, character_id=90000003, date=today - timedelta(days=10)
        )
        tasks.purge_old_maintenance_logs()
        self.assertFalse(PiMaintenanceLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(PiMaintenanceLog.objects.filter(pk=recent.pk).exists())
