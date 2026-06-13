"""
Extended view tests: all permission-protected pages + JSON endpoints.
"""
import json

from django.test import TestCase
from django.urls import reverse

from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

from aa_pi_tracker.models import (
    PiExtractorPin,
    PiFactoryPin,
    PiMarketPrice,
    PiOwner,
    PiPlanet,
    PiProject,
    PiProjectObjective,
    PiProjectPlanet,
    PiStorageItem,
)


def _make_user_with_perm(username, char_name, char_id):
    user = AuthUtils.create_user(username)
    AuthUtils.add_main_character(user, char_name, char_id, 98000001, "Test Corp", "TST")
    AuthUtils.add_permission_to_user_by_name("aa_pi_tracker.view_pi", user)
    return user


def _make_owner(user, char_id):
    char = EveCharacter.objects.get(character_id=char_id)
    return PiOwner.objects.create(user=user, character=char)


def _make_planet(owner, planet_id, planet_name="Test IV", planet_type="barren"):
    return PiPlanet.objects.create(
        owner=owner,
        planet_id=planet_id,
        planet_name=planet_name,
        planet_type=planet_type,
    )


class TestPageAccessControl(TestCase):
    """Verify all pages redirect without permission and return 200 with permission."""

    PAGES = [
        "extractors",
        "planets",
        "projects",
        "profit",
        "characters",
        "optimizer",
    ]

    @classmethod
    def setUpTestData(cls):
        cls.user_with_perm = _make_user_with_perm("perm_user", "Perm Char", 30000001)
        cls.user_no_perm = AuthUtils.create_user("noperm_user")

    def test_all_pages_redirect_when_not_logged_in(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                url = reverse(f"aa_pi_tracker:{page}")
                response = self.client.get(url)
                self.assertIn(response.status_code, [301, 302], msg=f"{page} should redirect")

    def test_all_pages_redirect_without_permission(self):
        self.client.force_login(self.user_no_perm)
        for page in self.PAGES:
            with self.subTest(page=page):
                url = reverse(f"aa_pi_tracker:{page}")
                response = self.client.get(url)
                self.assertIn(response.status_code, [301, 302])

    def test_all_pages_return_200_with_permission(self):
        self.client.force_login(self.user_with_perm)
        for page in self.PAGES:
            with self.subTest(page=page):
                url = reverse(f"aa_pi_tracker:{page}")
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, msg=f"{page} returned {response.status_code}")


class TestRemoveCharacterView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("remove_user", "Remove Char", 30000002)
        cls.owner = _make_owner(cls.user, 30000002)

    def test_remove_character_deletes_owner(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:remove_character"),
            {"owner_pk": self.owner.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertFalse(PiOwner.objects.filter(pk=self.owner.pk).exists())

    def test_remove_character_only_own_owner(self):
        """Cannot delete another user's owner by guessing PK."""
        other_user = _make_user_with_perm("other_user2", "Other Char2", 30000099)
        other_owner = _make_owner(other_user, 30000099)

        self.client.force_login(self.user)
        self.client.post(
            reverse("aa_pi_tracker:remove_character"),
            {"owner_pk": other_owner.pk},
        )
        # Other user's owner must still exist
        self.assertTrue(PiOwner.objects.filter(pk=other_owner.pk).exists())

    def test_remove_character_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_pi_tracker:remove_character"))
        self.assertEqual(response.status_code, 405)


class TestTriggerSyncView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("sync_user", "Sync Char", 30000003)

    def test_trigger_sync_returns_ok(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("aa_pi_tracker:trigger_sync"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_trigger_sync_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_pi_tracker:trigger_sync"))
        self.assertEqual(response.status_code, 405)


class TestTriggerPriceSyncView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("price_user", "Price Char", 30000004)

    def test_trigger_price_sync_returns_ok(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("aa_pi_tracker:trigger_price_sync"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])


class TestCreateProjectView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("create_proj", "Create Proj Char", 30000005)

    def test_create_project_success(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:create_project"),
            {"name": "My New Project"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["name"], "My New Project")
        self.assertTrue(PiProject.objects.filter(user=self.user, name="My New Project").exists())

    def test_create_project_missing_name_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("aa_pi_tracker:create_project"), {"name": ""})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data["ok"])

    def test_create_project_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_pi_tracker:create_project"))
        self.assertEqual(response.status_code, 405)


class TestDeleteProjectView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("del_proj", "Del Proj Char", 30000006)
        cls.project = PiProject.objects.create(user=cls.user, name="To Delete")

    def test_delete_own_project(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:delete_project", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(PiProject.objects.filter(pk=self.project.pk).exists())

    def test_delete_other_users_project_returns_404(self):
        other = _make_user_with_perm("other_del", "Other Del", 30000097)
        project_other = PiProject.objects.create(user=other, name="Other Project")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:delete_project", kwargs={"pk": project_other.pk})
        )
        self.assertEqual(response.status_code, 404)


class TestAddObjectiveView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("add_obj", "Add Obj Char", 30000007)
        cls.project = PiProject.objects.create(user=cls.user, name="Obj Project")

    def test_add_valid_objective(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:add_objective", kwargs={"pk": self.project.pk}),
            {"schematic_name": "Bacteria", "target_qty_per_hour": "2"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(
            PiProjectObjective.objects.filter(
                project=self.project, schematic_name="Bacteria"
            ).exists()
        )

    def test_add_unknown_schematic_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:add_objective", kwargs={"pk": self.project.pk}),
            {"schematic_name": "Tritanium", "target_qty_per_hour": "1"},
        )
        self.assertEqual(response.status_code, 400)

    def test_add_objective_to_other_users_project_returns_404(self):
        other = _make_user_with_perm("other_obj", "Other Obj", 30000096)
        project_other = PiProject.objects.create(user=other, name="Other Obj Project")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:add_objective", kwargs={"pk": project_other.pk}),
            {"schematic_name": "Bacteria", "target_qty_per_hour": "1"},
        )
        self.assertEqual(response.status_code, 404)


class TestEditObjectiveView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("edit_obj", "Edit Obj Char", 30000008)
        cls.project = PiProject.objects.create(user=cls.user, name="Edit Obj Project")
        cls.objective = PiProjectObjective.objects.create(
            project=cls.project, schematic_name="Water", target_qty_per_hour=1
        )

    def test_edit_objective_updates_quantity(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:edit_objective", kwargs={"pk": self.objective.pk}),
            {"target_qty_per_hour": "5"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.objective.refresh_from_db()
        self.assertEqual(self.objective.target_qty_per_hour, 5)


class TestDeleteObjectiveView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("del_obj", "Del Obj Char", 30000009)
        cls.project = PiProject.objects.create(user=cls.user, name="Del Obj Project")
        cls.objective = PiProjectObjective.objects.create(
            project=cls.project, schematic_name="Oxygen", target_qty_per_hour=1
        )

    def test_delete_objective(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:delete_objective", kwargs={"pk": self.objective.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(PiProjectObjective.objects.filter(pk=self.objective.pk).exists())


class TestAddRemoveProjectPlanetViews(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("pp_user", "PP User Char", 30000010)
        cls.owner = _make_owner(cls.user, 30000010)
        cls.planet = _make_planet(cls.owner, 40000400, "PP IV", "temperate")
        cls.project = PiProject.objects.create(user=cls.user, name="PP Project")

    def test_add_project_planet(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:add_project_planet", kwargs={"pk": self.project.pk}),
            {"planet_pk": self.planet.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["planet_name"], self.planet.planet_name)
        self.assertTrue(
            PiProjectPlanet.objects.filter(
                project=self.project, planet=self.planet
            ).exists()
        )

    def test_remove_project_planet(self):
        pp = PiProjectPlanet.objects.get_or_create(
            project=self.project, planet=self.planet
        )[0]
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:remove_project_planet", kwargs={"pk": pp.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertFalse(PiProjectPlanet.objects.filter(pk=pp.pk).exists())


class TestSetPlanetResourceView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("resource_user", "Resource Char", 30000011)
        cls.owner = _make_owner(cls.user, 30000011)
        cls.planet = _make_planet(cls.owner, 40000500, "Resource IV", "barren")

    def test_set_resource_success(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:set_planet_resource", kwargs={"planet_pk": self.planet.pk}),
            data=json.dumps({"resource": "Base Metals"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["resource"], "Base Metals")
        self.planet.refresh_from_db()
        self.assertEqual(self.planet.user_resource, "Base Metals")

    def test_set_resource_clear(self):
        self.client.force_login(self.user)
        self.planet.user_resource = "Base Metals"
        self.planet.save()
        response = self.client.post(
            reverse("aa_pi_tracker:set_planet_resource", kwargs={"planet_pk": self.planet.pk}),
            data=json.dumps({"resource": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.planet.refresh_from_db()
        self.assertEqual(self.planet.user_resource, "")

    def test_set_resource_other_planet_returns_404(self):
        other = _make_user_with_perm("other_res", "Other Res", 30000095)
        other_owner = _make_owner(other, 30000095)
        other_planet = _make_planet(other_owner, 40000501, "Other IV")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:set_planet_resource", kwargs={"planet_pk": other_planet.pk}),
            data=json.dumps({"resource": "Base Metals"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_set_resource_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:set_planet_resource", kwargs={"planet_pk": self.planet.pk}),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_set_resource_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("aa_pi_tracker:set_planet_resource", kwargs={"planet_pk": self.planet.pk})
        )
        self.assertEqual(response.status_code, 405)


class TestProjectAnalysisJsonView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("proj_json", "Proj JSON Char", 30000012)
        cls.project = PiProject.objects.create(user=cls.user, name="Analysis Project")

    def test_returns_json(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("aa_pi_tracker:project_analysis_json", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("planet_assignments", data)
        self.assertIn("fabrication_flat", data)

    def test_other_users_project_returns_404(self):
        other = _make_user_with_perm("other_json", "Other JSON", 30000094)
        project_other = PiProject.objects.create(user=other, name="Other Analysis")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("aa_pi_tracker:project_analysis_json", kwargs={"pk": project_other.pk})
        )
        self.assertEqual(response.status_code, 404)


class TestPlanetOptimizerJsonView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("optim_json", "Optim JSON Char", 30000013)
        cls.owner = _make_owner(cls.user, 30000013)
        cls.planet = _make_planet(cls.owner, 40000600, "Optim IV", "barren")

    def test_returns_suggestions(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("aa_pi_tracker:planet_optimizer_json", kwargs={"planet_pk": self.planet.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("p1_chains", data)
        self.assertIn("p2_chains", data)

    def test_other_users_planet_returns_404(self):
        other = _make_user_with_perm("other_optim", "Other Optim", 30000093)
        other_owner = _make_owner(other, 30000093)
        other_planet = _make_planet(other_owner, 40000601, "Other Optim IV")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("aa_pi_tracker:planet_optimizer_json", kwargs={"planet_pk": other_planet.pk})
        )
        self.assertEqual(response.status_code, 404)


class TestOptimizerAnalyzeJsonView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("optim_analyze", "Optim Analyze", 30000014)
        # Add an owner with IC skill so optimizer has slot data
        cls.owner = _make_owner(cls.user, 30000014)
        cls.owner.interplanetary_consolidation = 5
        cls.owner.save()

    def test_invalid_mode_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_analyze_json"),
            data=json.dumps({"mode": "unknown"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_target_mode_missing_target_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_analyze_json"),
            data=json.dumps({"mode": "target", "target": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_pi_tracker:optimizer_analyze_json"))
        self.assertEqual(response.status_code, 405)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_analyze_json"),
            data="not json",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_max_isk_mode_returns_result(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_analyze_json"),
            data=json.dumps({"mode": "max_isk"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIsInstance(data["result"], list)

    def test_target_mode_valid_schematic(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_analyze_json"),
            data=json.dumps({"mode": "target", "target": "Bacteria"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["result"]["target"], "Bacteria")


class TestOptimizerCreateProjectView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("optim_create", "Optim Create", 30000015)
        cls.owner = _make_owner(cls.user, 30000015)
        cls.planet = _make_planet(cls.owner, 40000700, "Optim Create IV", "barren")

    def test_create_project_from_optimizer(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_create_project"),
            data=json.dumps({
                "name": "Optimizer Project",
                "assignments": [{"pk": self.planet.pk, "role": "miner", "p0": "Base Metals"}],
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(PiProject.objects.filter(user=self.user, name="Optimizer Project").exists())

    def test_requires_name(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_create_project"),
            data=json.dumps({
                "name": "",
                "assignments": [{"pk": self.planet.pk, "role": "miner", "p0": "Base Metals"}],
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_requires_planets(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("aa_pi_tracker:optimizer_create_project"),
            data=json.dumps({"name": "No Planets", "assignments": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_pi_tracker:optimizer_create_project"))
        self.assertEqual(response.status_code, 405)


class TestViewHelperFunctions(TestCase):
    """Tests for fmt_cycle, fmt_remaining, sec_class, sec_display utility functions."""

    def test_fmt_cycle_minutes(self):
        from aa_pi_tracker.views.helpers import fmt_cycle
        self.assertEqual(fmt_cycle(1800), "30m")
        self.assertEqual(fmt_cycle(900), "15m")

    def test_fmt_cycle_hours(self):
        from aa_pi_tracker.views.helpers import fmt_cycle
        self.assertEqual(fmt_cycle(3600), "1h 0m")
        self.assertEqual(fmt_cycle(5400), "1h 30m")

    def test_fmt_remaining_none(self):
        from aa_pi_tracker.views.helpers import fmt_remaining
        from django.utils import timezone
        display, urgency = fmt_remaining(None, timezone.now())
        self.assertEqual(display, "—")
        self.assertEqual(urgency, "ok")

    def test_fmt_remaining_expired(self):
        from aa_pi_tracker.views.helpers import fmt_remaining
        from django.utils import timezone
        from datetime import timedelta
        past = timezone.now() - timedelta(hours=1)
        display, urgency = fmt_remaining(past, timezone.now())
        self.assertEqual(display, "EXPIRED")
        self.assertEqual(urgency, "expired")

    def test_fmt_remaining_critical(self):
        from aa_pi_tracker.views.helpers import fmt_remaining
        from django.utils import timezone
        from datetime import timedelta
        soon = timezone.now() + timedelta(hours=2)
        display, urgency = fmt_remaining(soon, timezone.now())
        self.assertEqual(urgency, "critical")

    def test_fmt_remaining_warning(self):
        from aa_pi_tracker.views.helpers import fmt_remaining
        from django.utils import timezone
        from datetime import timedelta
        later = timezone.now() + timedelta(hours=10)
        display, urgency = fmt_remaining(later, timezone.now())
        self.assertEqual(urgency, "warning")

    def test_fmt_remaining_ok(self):
        from aa_pi_tracker.views.helpers import fmt_remaining
        from django.utils import timezone
        from datetime import timedelta
        far = timezone.now() + timedelta(days=2)
        display, urgency = fmt_remaining(far, timezone.now())
        self.assertEqual(urgency, "ok")

    def test_sec_class_and_display(self):
        from aa_pi_tracker.views.helpers import sec_class, sec_display
        self.assertEqual(sec_class(0.9), "success")
        self.assertEqual(sec_class(0.3), "warning")
        self.assertEqual(sec_class(-0.1), "danger")
        self.assertEqual(sec_class(None), "secondary")
        self.assertEqual(sec_display(0.9), "0.9")
        self.assertEqual(sec_display(None), "?")


class TestBuildProfitData(TestCase):
    """Tests for _build_profit_data — profit calculations."""

    def test_empty_prices_returns_zero_profit(self):
        from aa_pi_tracker.views.profit import _build_profit_data
        rows = _build_profit_data({})
        self.assertTrue(len(rows) > 0)
        # All profits should be zero without price data
        for row in rows:
            self.assertEqual(row["profit_per_hour"], 0.0)

    def test_with_prices_calculates_profit(self):
        from aa_pi_tracker.views.profit import _build_profit_data
        prices = {"Bacteria": 500.0, "Microorganisms": 10.0}
        rows = _build_profit_data(prices)
        bac = next((r for r in rows if r["name"] == "Bacteria"), None)
        self.assertIsNotNone(bac)
        self.assertEqual(bac["tier"], 1)
        self.assertGreater(bac["output_qty_per_hour"], 0)

    def test_rows_sorted_by_profit_desc(self):
        from aa_pi_tracker.views.profit import _build_profit_data
        prices = {
            "Bacteria": 1000.0,
            "Water": 1.0,
            "Microorganisms": 0.0,
            "Aqueous Liquids": 0.0,
        }
        rows = _build_profit_data(prices)
        profits = [r["profit_per_hour"] for r in rows]
        self.assertEqual(profits, sorted(profits, reverse=True))


class TestSystemSearchView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_with_perm("sys_search", "Sys Search Char", 30000016)

    def test_short_query_returns_empty(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_pi_tracker:system_search"), {"q": "J"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["results"], [])

    def test_valid_query_returns_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("aa_pi_tracker:system_search"), {"q": "Jita"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("results", data)
        self.assertIsInstance(data["results"], list)
