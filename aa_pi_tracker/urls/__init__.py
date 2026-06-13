from django.urls import include, path

app_name = "aa_pi_tracker"

urlpatterns = [
    path("", include("aa_pi_tracker.urls.pages")),
    path("", include("aa_pi_tracker.urls.characters")),
    path("", include("aa_pi_tracker.urls.planets")),
    path("", include("aa_pi_tracker.urls.projects")),
    path("", include("aa_pi_tracker.urls.optimizer")),
    path("", include("aa_pi_tracker.urls.buildout")),
    path("corp/", include("aa_pi_tracker.urls.corp_projects")),
]
