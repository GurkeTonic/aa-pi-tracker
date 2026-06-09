from django.utils.translation import gettext_lazy as _

from allianceauth import hooks
from allianceauth.services.hooks import MenuItemHook, UrlHook

from . import urls


class PiTrackerMenuItem(MenuItemHook):
    def __init__(self):
        super().__init__(
            _("PI Tracker"),
            "fas fa-globe",
            "aa_pi_tracker:index",
            navactive=["aa_pi_tracker:"],
        )

    def render(self, request):
        if request.user.has_perm("aa_pi_tracker.view_pi"):
            return super().render(request)
        return ""


@hooks.register("menu_item_hook")
def register_menu():
    return PiTrackerMenuItem()


@hooks.register("url_hook")
def register_url():
    return UrlHook(urls, "aa_pi_tracker", r"^pi-tracker/")
