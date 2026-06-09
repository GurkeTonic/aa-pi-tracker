from django.test import TestCase
from django.urls import reverse

from allianceauth.tests.auth_utils import AuthUtils


class TestIndexView(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_no_perm = AuthUtils.create_user("noperm")
        AuthUtils.add_main_character(
            cls.user_no_perm, "No Perm Char", 11111111, 98000001, "Test Corp", "TST"
        )
        cls.user_with_perm = AuthUtils.create_user("withperm")
        AuthUtils.add_main_character(
            cls.user_with_perm, "Perm Char", 22222222, 98000001, "Test Corp", "TST"
        )
        AuthUtils.add_permission_to_user_by_name("aa_pi_tracker.view_pi", cls.user_with_perm)

    def test_redirect_when_not_logged_in(self):
        response = self.client.get(reverse("aa_pi_tracker:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_no_access_without_permission(self):
        self.client.force_login(self.user_no_perm)
        response = self.client.get(reverse("aa_pi_tracker:index"))
        self.assertEqual(response.status_code, 302)

    def test_ok_with_permission(self):
        self.client.force_login(self.user_with_perm)
        response = self.client.get(reverse("aa_pi_tracker:index"))
        self.assertEqual(response.status_code, 200)
