"""
Tests for previously untested views:
- buildout_page, maintenance_page, maintenance_char_page
- corp_projects views (manage_corp_pi permission)
- _build_buildout_data, _build_maintenance_overview logic
"""

# Django
from django.test import TestCase
from django.urls import reverse

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter
from allianceauth.tests.auth_utils import AuthUtils

# AA PI Tracker
from aa_pi_tracker.models import (
    PiExtractorPin,
    PiOwner,
    PiPlanet,
    PiProject,
    PiProjectObjective,
    PiProjectPlanet,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_view_pi(username, char_name, char_id):
    user = AuthUtils.create_member(username)
    AuthUtils.add_main_character_2(
        user,
        char_name,
        character_id=char_id,
        corp_id=98000001,
        corp_name="Test Corp",
    )
    AuthUtils.add_permission_to_user_by_name("aa_pi_tracker.view_pi", user)
    return user


def _make_user_manage_corp(username, char_name, char_id, corp_id=98000001):
    user = AuthUtils.create_member(username)
    AuthUtils.add_main_character_2(
        user,
        char_name,
        character_id=char_id,
        corp_id=corp_id,
        corp_name="Test Corp",
    )
    AuthUtils.add_permission_to_user_by_name("aa_pi_tracker.manage_corp_pi", user)
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


# ---------------------------------------------------------------------------
# buildout_page
# ---------------------------------------------------------------------------


class TestBuildoutPage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_view_pi("bo_user", "Buildout Char", 90000010)
        cls.owner = _make_owner(cls.user, 90000010)
        cls.planet = _make_planet(cls.owner, 40001000, "BO IV", "barren")
        cls.project = PiProject.objects.create(user=cls.user, name="Buildout Project")
        PiProjectPlanet.objects.create(
            project=cls.project,
            planet=cls.planet,
            role=PiProjectPlanet.ROLE_MINER,
            assigned_p0="Base Metals",
        )

    def test_unauthenticated_redirects(self):
        res = self.client.get(
            reverse("aa_pi_tracker:buildout_page", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(res.status_code, 302)

    def test_no_permission_redirects(self):
        user_no_perm = AuthUtils.create_member("bo_noperm")
        AuthUtils.add_main_character_2(
            user_no_perm,
            "No Perm",
            character_id=90000011,
            corp_id=98000001,
            corp_name="Test Corp",
        )
        self.client.force_login(user_no_perm)
        res = self.client.get(
            reverse("aa_pi_tracker:buildout_page", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(res.status_code, 302)

    def test_returns_200_with_permission(self):
        self.client.force_login(self.user)
        res = self.client.get(
            reverse("aa_pi_tracker:buildout_page", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "aa_pi_tracker/view/buildout.html")

    def test_other_users_project_returns_404(self):
        other = _make_user_view_pi("bo_other", "Other BO", 90000012)
        other_project = PiProject.objects.create(user=other, name="Other BO Project")
        self.client.force_login(self.user)
        res = self.client.get(
            reverse("aa_pi_tracker:buildout_page", kwargs={"pk": other_project.pk})
        )
        self.assertEqual(res.status_code, 404)

    def test_context_contains_chars_data(self):
        self.client.force_login(self.user)
        res = self.client.get(
            reverse("aa_pi_tracker:buildout_page", kwargs={"pk": self.project.pk})
        )
        self.assertIn("chars_data", res.context)
        self.assertIn("project", res.context)


# ---------------------------------------------------------------------------
# maintenance_page
# ---------------------------------------------------------------------------


class TestMaintenancePage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_view_pi("maint_user", "Maint Char", 90000020)
        cls.owner = _make_owner(cls.user, 90000020)
        cls.planet = _make_planet(cls.owner, 40002000, "Maint IV", "temperate")
        cls.project = PiProject.objects.create(user=cls.user, name="Maint Project")
        PiProjectPlanet.objects.create(
            project=cls.project,
            planet=cls.planet,
            role=PiProjectPlanet.ROLE_MINER,
            assigned_p0="Microorganisms",
        )

    def test_unauthenticated_redirects(self):
        res = self.client.get(
            reverse("aa_pi_tracker:maintenance_page", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(res.status_code, 302)

    def test_no_permission_redirects(self):
        user_no_perm = AuthUtils.create_member("maint_noperm")
        AuthUtils.add_main_character_2(
            user_no_perm,
            "No Perm Maint",
            character_id=90000021,
            corp_id=98000001,
            corp_name="Test Corp",
        )
        self.client.force_login(user_no_perm)
        res = self.client.get(
            reverse("aa_pi_tracker:maintenance_page", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(res.status_code, 302)

    def test_returns_200_with_permission(self):
        self.client.force_login(self.user)
        res = self.client.get(
            reverse("aa_pi_tracker:maintenance_page", kwargs={"pk": self.project.pk})
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "aa_pi_tracker/view/maintenance.html")

    def test_other_users_project_returns_404(self):
        other = _make_user_view_pi("maint_other", "Other Maint", 90000022)
        other_project = PiProject.objects.create(user=other, name="Other Maint Project")
        self.client.force_login(self.user)
        res = self.client.get(
            reverse("aa_pi_tracker:maintenance_page", kwargs={"pk": other_project.pk})
        )
        self.assertEqual(res.status_code, 404)

    def test_context_keys(self):
        self.client.force_login(self.user)
        res = self.client.get(
            reverse("aa_pi_tracker:maintenance_page", kwargs={"pk": self.project.pk})
        )
        for key in (
            "chars_data",
            "project",
            "total_expired",
            "total_critical",
            "total_chars",
        ):
            self.assertIn(key, res.context)


# ---------------------------------------------------------------------------
# maintenance_char_page
# ---------------------------------------------------------------------------


class TestMaintenanceCharPage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_view_pi("mc_user", "MC Char", 90000030)
        cls.owner = _make_owner(cls.user, 90000030)
        cls.planet = _make_planet(cls.owner, 40003000, "MC IV", "barren")
        cls.project = PiProject.objects.create(user=cls.user, name="MC Project")
        PiProjectPlanet.objects.create(
            project=cls.project,
            planet=cls.planet,
            role=PiProjectPlanet.ROLE_MINER,
            assigned_p0="Base Metals",
        )

    def test_returns_200_with_permission(self):
        self.client.force_login(self.user)
        res = self.client.get(
            reverse(
                "aa_pi_tracker:maintenance_char_page",
                kwargs={"pk": self.project.pk, "char_pk": 90000030},
            )
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "aa_pi_tracker/view/maintenance_char.html")

    def test_unauthenticated_redirects(self):
        res = self.client.get(
            reverse(
                "aa_pi_tracker:maintenance_char_page",
                kwargs={"pk": self.project.pk, "char_pk": 90000030},
            )
        )
        self.assertEqual(res.status_code, 302)

    def test_other_users_project_returns_404(self):
        other = _make_user_view_pi("mc_other", "MC Other", 90000031)
        other_project = PiProject.objects.create(user=other, name="MC Other Project")
        self.client.force_login(self.user)
        res = self.client.get(
            reverse(
                "aa_pi_tracker:maintenance_char_page",
                kwargs={"pk": other_project.pk, "char_pk": 90000030},
            )
        )
        self.assertEqual(res.status_code, 404)

    def test_context_keys(self):
        self.client.force_login(self.user)
        res = self.client.get(
            reverse(
                "aa_pi_tracker:maintenance_char_page",
                kwargs={"pk": self.project.pk, "char_pk": 90000030},
            )
        )
        for key in (
            "project",
            "char_pk",
            "step1_planets",
            "step2_planets",
            "step3_planets",
        ):
            self.assertIn(key, res.context)


# ---------------------------------------------------------------------------
# corp_projects_member_page
# ---------------------------------------------------------------------------


class TestCorpProjectsMemberPage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_view_pi("cpm_user", "CPM Char", 90000040)

    def test_unauthenticated_redirects(self):
        res = self.client.get(reverse("aa_pi_tracker:corp_projects_member"))
        self.assertEqual(res.status_code, 302)

    def test_no_permission_redirects(self):
        user_no_perm = AuthUtils.create_member("cpm_noperm")
        AuthUtils.add_main_character_2(
            user_no_perm,
            "No Perm CPM",
            character_id=90000041,
            corp_id=98000001,
            corp_name="Test Corp",
        )
        self.client.force_login(user_no_perm)
        res = self.client.get(reverse("aa_pi_tracker:corp_projects_member"))
        self.assertEqual(res.status_code, 302)

    def test_returns_200_with_view_pi(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse("aa_pi_tracker:corp_projects_member"))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "aa_pi_tracker/view/corp_projects_member.html")


# ---------------------------------------------------------------------------
# corp_projects_page (requires manage_corp_pi)
# ---------------------------------------------------------------------------


class TestCorpProjectsPage(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = _make_user_manage_corp("cp_manager", "CP Manager", 90000050)
        cls.view_only = _make_user_view_pi("cp_view", "CP View Only", 90000051)

    def test_unauthenticated_redirects(self):
        res = self.client.get(reverse("aa_pi_tracker:corp_projects"))
        self.assertEqual(res.status_code, 302)

    def test_view_pi_only_redirects(self):
        # view_pi without manage_corp_pi → redirect
        self.client.force_login(self.view_only)
        res = self.client.get(reverse("aa_pi_tracker:corp_projects"))
        self.assertEqual(res.status_code, 302)

    def test_manage_corp_pi_returns_200(self):
        self.client.force_login(self.manager)
        res = self.client.get(reverse("aa_pi_tracker:corp_projects"))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "aa_pi_tracker/view/corp_projects.html")

    def test_context_keys(self):
        self.client.force_login(self.manager)
        res = self.client.get(reverse("aa_pi_tracker:corp_projects"))
        for key in ("corp_projects", "shared_owners", "schematic_choices"):
            self.assertIn(key, res.context)


# ---------------------------------------------------------------------------
# toggle_share_character
# ---------------------------------------------------------------------------


class TestToggleShareCharacter(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_view_pi("tsc_user", "TSC Char", 90000060)
        cls.owner = _make_owner(cls.user, 90000060)

    def test_toggle_sets_shared_true(self):
        self.assertFalse(self.owner.shared_with_corp)
        self.client.force_login(self.user)
        res = self.client.post(
            reverse("aa_pi_tracker:toggle_share_character"),
            {"owner_pk": self.owner.pk},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["shared"])
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.shared_with_corp)

    def test_toggle_twice_resets_to_false(self):
        self.owner.shared_with_corp = True
        self.owner.save()
        self.client.force_login(self.user)
        res = self.client.post(
            reverse("aa_pi_tracker:toggle_share_character"),
            {"owner_pk": self.owner.pk},
        )
        data = res.json()
        self.assertFalse(data["shared"])

    def test_toggle_other_users_owner_returns_404(self):
        other = _make_user_view_pi("tsc_other", "TSC Other", 90000061)
        other_owner = _make_owner(other, 90000061)
        self.client.force_login(self.user)
        res = self.client.post(
            reverse("aa_pi_tracker:toggle_share_character"),
            {"owner_pk": other_owner.pk},
        )
        self.assertEqual(res.status_code, 404)

    def test_requires_post(self):
        self.client.force_login(self.user)
        res = self.client.get(reverse("aa_pi_tracker:toggle_share_character"))
        self.assertEqual(res.status_code, 405)


# ---------------------------------------------------------------------------
# create_corp_project
# ---------------------------------------------------------------------------


class TestCreateCorpProject(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = _make_user_manage_corp("ccp_manager", "CCP Manager", 90000070)

    def test_create_corp_project_success(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse("aa_pi_tracker:create_corp_project"),
            {"name": "Corp Alpha"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["name"], "Corp Alpha")
        self.assertTrue(
            PiProject.objects.filter(
                user=self.manager, name="Corp Alpha", is_corp_project=True
            ).exists()
        )

    def test_create_corp_project_missing_name_returns_400(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse("aa_pi_tracker:create_corp_project"), {"name": ""}
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["ok"])

    def test_create_corp_project_requires_manage_corp_pi(self):
        view_only = _make_user_view_pi("ccp_viewonly", "CCP View", 90000071)
        self.client.force_login(view_only)
        res = self.client.post(
            reverse("aa_pi_tracker:create_corp_project"), {"name": "Denied"}
        )
        self.assertEqual(res.status_code, 302)

    def test_requires_post(self):
        self.client.force_login(self.manager)
        res = self.client.get(reverse("aa_pi_tracker:create_corp_project"))
        self.assertEqual(res.status_code, 405)


# ---------------------------------------------------------------------------
# delete_corp_project
# ---------------------------------------------------------------------------


class TestDeleteCorpProject(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = _make_user_manage_corp("dcp_manager", "DCP Manager", 90000080)

    def test_delete_own_corp_project(self):
        project = PiProject.objects.create(
            user=self.manager, name="To Delete Corp", is_corp_project=True
        )
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse("aa_pi_tracker:delete_corp_project", kwargs={"pk": project.pk})
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertFalse(PiProject.objects.filter(pk=project.pk).exists())

    def test_delete_other_users_corp_project_returns_404(self):
        other_manager = _make_user_manage_corp("dcp_other", "DCP Other", 90000081)
        project = PiProject.objects.create(
            user=other_manager, name="Other Corp Project", is_corp_project=True
        )
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse("aa_pi_tracker:delete_corp_project", kwargs={"pk": project.pk})
        )
        self.assertEqual(res.status_code, 404)

    def test_delete_non_corp_project_returns_404(self):
        project = PiProject.objects.create(
            user=self.manager, name="Regular Project", is_corp_project=False
        )
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse("aa_pi_tracker:delete_corp_project", kwargs={"pk": project.pk})
        )
        self.assertEqual(res.status_code, 404)


# ---------------------------------------------------------------------------
# corp_project_set_participants
# ---------------------------------------------------------------------------


class TestCorpProjectSetParticipants(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = _make_user_manage_corp(
            "prt_manager", "PRT Manager", 90000090, corp_id=98000099
        )
        cls.project = PiProject.objects.create(
            user=cls.manager, name="Participants Project", is_corp_project=True
        )
        # Create a shared owner in the same corp
        cls.member_user = _make_user_view_pi("prt_member", "PRT Member", 90000091)
        cls.member_owner = _make_owner(cls.member_user, 90000091)
        # Update the member's character corp to match manager's corp
        member_char = EveCharacter.objects.get(character_id=90000091)
        member_char.corporation_id = 98000099
        member_char.save()
        cls.member_owner.shared_with_corp = True
        cls.member_owner.save()

    def test_set_participants_success(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_set_participants",
                kwargs={"pk": self.project.pk},
            ),
            {"owner_pks[]": [self.member_owner.pk]},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])

    def test_set_participants_requires_manage_corp_pi(self):
        view_only = _make_user_view_pi("prt_view", "PRT View", 90000092)
        self.client.force_login(view_only)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_set_participants",
                kwargs={"pk": self.project.pk},
            ),
            {"owner_pks[]": []},
        )
        self.assertEqual(res.status_code, 302)


# ---------------------------------------------------------------------------
# corp_project_add_objective
# ---------------------------------------------------------------------------


class TestCorpProjectAddObjective(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = _make_user_manage_corp("cao_manager", "CAO Manager", 90000030)
        cls.project = PiProject.objects.create(
            user=cls.manager, name="CAO Project", is_corp_project=True
        )

    def test_add_valid_objective(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_add_objective",
                kwargs={"pk": self.project.pk},
            ),
            {"schematic_name": "Bacteria", "target_qty_per_hour": "3"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["schematic_name"], "Bacteria")
        self.assertTrue(
            PiProjectObjective.objects.filter(
                project=self.project, schematic_name="Bacteria"
            ).exists()
        )

    def test_add_unknown_schematic_returns_400(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_add_objective",
                kwargs={"pk": self.project.pk},
            ),
            {"schematic_name": "Tritanium", "target_qty_per_hour": "1"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()["ok"])

    def test_add_objective_to_other_users_project_returns_404(self):
        other = _make_user_manage_corp("cao_other", "CAO Other", 90000031)
        other_project = PiProject.objects.create(
            user=other, name="Other CAO", is_corp_project=True
        )
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_add_objective",
                kwargs={"pk": other_project.pk},
            ),
            {"schematic_name": "Bacteria", "target_qty_per_hour": "1"},
        )
        self.assertEqual(res.status_code, 404)

    def test_update_or_create_same_schematic(self):
        """Adding the same schematic twice updates the quantity (no duplicate)."""
        self.client.force_login(self.manager)
        self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_add_objective",
                kwargs={"pk": self.project.pk},
            ),
            {"schematic_name": "Water", "target_qty_per_hour": "2"},
        )
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_add_objective",
                kwargs={"pk": self.project.pk},
            ),
            {"schematic_name": "Water", "target_qty_per_hour": "5"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            PiProjectObjective.objects.filter(
                project=self.project, schematic_name="Water"
            ).count(),
            1,
        )
        obj = PiProjectObjective.objects.get(
            project=self.project, schematic_name="Water"
        )
        self.assertEqual(obj.target_qty_per_hour, 5)


# ---------------------------------------------------------------------------
# corp_project_delete_objective
# ---------------------------------------------------------------------------


class TestCorpProjectDeleteObjective(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = _make_user_manage_corp("cdo_manager", "CDO Manager", 90000032)
        cls.project = PiProject.objects.create(
            user=cls.manager, name="CDO Project", is_corp_project=True
        )
        cls.objective = PiProjectObjective.objects.create(
            project=cls.project, schematic_name="Oxygen", target_qty_per_hour=1
        )

    def test_delete_objective_success(self):
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_delete_objective",
                kwargs={"pk": self.objective.pk},
            )
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ok"])
        self.assertFalse(
            PiProjectObjective.objects.filter(pk=self.objective.pk).exists()
        )

    def test_delete_objective_other_user_returns_404(self):
        other = _make_user_manage_corp("cdo_other", "CDO Other", 90000033)
        other_project = PiProject.objects.create(
            user=other, name="CDO Other", is_corp_project=True
        )
        other_obj = PiProjectObjective.objects.create(
            project=other_project, schematic_name="Water", target_qty_per_hour=1
        )
        self.client.force_login(self.manager)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_delete_objective",
                kwargs={"pk": other_obj.pk},
            )
        )
        self.assertEqual(res.status_code, 404)

    def test_requires_manage_corp_pi(self):
        objective = PiProjectObjective.objects.create(
            project=self.project, schematic_name="Electrolytes", target_qty_per_hour=1
        )
        view_only = _make_user_view_pi("cdo_view", "CDO View", 90000034)
        self.client.force_login(view_only)
        res = self.client.post(
            reverse(
                "aa_pi_tracker:corp_project_delete_objective",
                kwargs={"pk": objective.pk},
            )
        )
        self.assertEqual(res.status_code, 302)


# ---------------------------------------------------------------------------
# _build_buildout_data logic
# ---------------------------------------------------------------------------


class TestBuildBuildoutData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = _make_user_view_pi("bbd_user", "BBD Char", 90000035)
        cls.owner = _make_owner(cls.user, 90000035)
        cls.planet_miner = _make_planet(cls.owner, 40004000, "BBD Miner IV", "barren")
        cls.planet_factory = _make_planet(
            cls.owner, 40004001, "BBD Factory IV", "barren"
        )
        cls.project = PiProject.objects.create(user=cls.user, name="BBD Project")
        PiProjectObjective.objects.create(
            project=cls.project, schematic_name="Bacteria", target_qty_per_hour=1
        )
        PiProjectPlanet.objects.create(
            project=cls.project,
            planet=cls.planet_miner,
            role=PiProjectPlanet.ROLE_MINER,
            assigned_p0="Microorganisms",
        )
        PiProjectPlanet.objects.create(
            project=cls.project,
            planet=cls.planet_factory,
            role=PiProjectPlanet.ROLE_FACTORY,
            assigned_p0="",
        )

    def test_miner_entry_has_role_and_extracts(self):
        # AA PI Tracker
        from aa_pi_tracker.views.buildout import _build_buildout_data

        chars_data = _build_buildout_data(self.project)
        # Flatten all planets from all characters
        all_planets = [p for c in chars_data for p in c["planets"]]
        miners = [p for p in all_planets if p["role"] == PiProjectPlanet.ROLE_MINER]
        self.assertEqual(len(miners), 1)
        self.assertEqual(miners[0]["extracts"], "Microorganisms")

    def test_factory_entry_has_aif_breakdown(self):
        # AA PI Tracker
        from aa_pi_tracker.views.buildout import _build_buildout_data

        chars_data = _build_buildout_data(self.project)
        all_planets = [p for c in chars_data for p in c["planets"]]
        factories = [
            p
            for p in all_planets
            if p["role"]
            in (PiProjectPlanet.ROLE_FACTORY, PiProjectPlanet.ROLE_FACTORY_P4)
        ]
        self.assertEqual(len(factories), 1)
        self.assertIsInstance(factories[0]["aif_breakdown"], list)

    def test_user_filter_excludes_other_users(self):
        # AA PI Tracker
        from aa_pi_tracker.views.buildout import _build_buildout_data

        other = _make_user_view_pi("bbd_other", "BBD Other", 90000036)
        other_owner = _make_owner(other, 90000036)
        other_planet = _make_planet(other_owner, 40004002, "BBD Other IV", "barren")
        PiProjectPlanet.objects.create(
            project=self.project,
            planet=other_planet,
            role=PiProjectPlanet.ROLE_MINER,
            assigned_p0="Base Metals",
        )
        chars_data_filtered = _build_buildout_data(self.project, user_filter=self.user)
        chars_data_all = _build_buildout_data(self.project, user_filter=None)
        total_filtered = sum(len(c["planets"]) for c in chars_data_filtered)
        total_all = sum(len(c["planets"]) for c in chars_data_all)
        self.assertLess(total_filtered, total_all)

    def test_empty_project_returns_empty_list(self):
        # AA PI Tracker
        from aa_pi_tracker.views.buildout import _build_buildout_data

        empty_project = PiProject.objects.create(user=self.user, name="Empty BBD")
        result = _build_buildout_data(empty_project)
        self.assertEqual(result, [])


# ---------------------------------------------------------------------------
# _build_maintenance_overview logic
# ---------------------------------------------------------------------------


class TestBuildMaintenanceOverview(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Standard Library
        from datetime import timedelta

        # Django
        from django.utils import timezone

        cls.user = _make_user_view_pi("bmo_user", "BMO Char", 90000037)
        cls.owner = _make_owner(cls.user, 90000037)
        cls.planet = _make_planet(cls.owner, 40005000, "BMO IV", "barren")
        cls.project = PiProject.objects.create(user=cls.user, name="BMO Project")
        cls.pp = PiProjectPlanet.objects.create(
            project=cls.project,
            planet=cls.planet,
            role=PiProjectPlanet.ROLE_MINER,
            assigned_p0="Base Metals",
        )
        now = timezone.now()
        # Expired extractor
        PiExtractorPin.objects.create(
            planet=cls.planet,
            product_type_id=2267,
            product_name="Base Metals",
            cycle_time=1800,
            qty_per_cycle=100,
            expiry_time=now - timedelta(hours=2),
        )

    def test_expired_extractor_counted(self):
        # Django
        from django.utils import timezone

        # AA PI Tracker
        from aa_pi_tracker.views.maintenance import _build_maintenance_overview

        result = _build_maintenance_overview(self.project, timezone.now())
        self.assertEqual(len(result), 1)
        char_entry = result[0]
        self.assertEqual(char_entry["expired_count"], 1)
        self.assertTrue(char_entry["has_issues"])

    def test_user_filter_excludes_other_users(self):
        # Django
        from django.utils import timezone

        # AA PI Tracker
        from aa_pi_tracker.views.maintenance import _build_maintenance_overview

        other = _make_user_view_pi("bmo_other", "BMO Other", 90000038)
        other_owner = _make_owner(other, 90000038)
        other_planet = _make_planet(other_owner, 40005001, "BMO Other IV", "barren")
        PiProjectPlanet.objects.create(
            project=self.project,
            planet=other_planet,
            role=PiProjectPlanet.ROLE_MINER,
            assigned_p0="Base Metals",
        )
        filtered = _build_maintenance_overview(
            self.project, timezone.now(), user_filter=self.user
        )
        all_chars = _build_maintenance_overview(
            self.project, timezone.now(), user_filter=None
        )
        filter_names = {c["char_name"] for c in filtered}
        all_names = {c["char_name"] for c in all_chars}
        self.assertNotIn("BMO Other", filter_names)
        self.assertIn("BMO Other", all_names)

    def test_empty_project_returns_empty(self):
        # Django
        from django.utils import timezone

        # AA PI Tracker
        from aa_pi_tracker.views.maintenance import _build_maintenance_overview

        empty = PiProject.objects.create(user=self.user, name="Empty BMO")
        result = _build_maintenance_overview(empty, timezone.now())
        self.assertEqual(result, [])
