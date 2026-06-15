# Django
from django.urls import path

from .. import views

urlpatterns = [
    path("", views.corp_projects_page, name="corp_projects"),
    path("member/", views.corp_projects_member_page, name="corp_projects_member"),
    path("toggle-share/", views.toggle_share_character, name="toggle_share_character"),
    path("create/", views.create_corp_project, name="create_corp_project"),
    path("<int:pk>/delete/", views.delete_corp_project, name="delete_corp_project"),
    path(
        "<int:pk>/participants/",
        views.corp_project_set_participants,
        name="corp_project_set_participants",
    ),
    path(
        "<int:pk>/add-objective/",
        views.corp_project_add_objective,
        name="corp_project_add_objective",
    ),
    path(
        "objective/<int:pk>/delete/",
        views.corp_project_delete_objective,
        name="corp_project_delete_objective",
    ),
]
