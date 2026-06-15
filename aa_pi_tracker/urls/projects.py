# Django
from django.urls import path

from .. import views

urlpatterns = [
    path("project/create/", views.create_project, name="create_project"),
    path("project/<int:pk>/delete/", views.delete_project, name="delete_project"),
    path("project/<int:pk>/add-objective/", views.add_objective, name="add_objective"),
    path(
        "project/<int:pk>/add-planet/",
        views.add_project_planet,
        name="add_project_planet",
    ),
    path(
        "project/<int:pk>/analysis.json",
        views.project_analysis_json,
        name="project_analysis_json",
    ),
    path("objective/<int:pk>/edit/", views.edit_objective, name="edit_objective"),
    path("objective/<int:pk>/delete/", views.delete_objective, name="delete_objective"),
    path(
        "project-planet/<int:pk>/remove/",
        views.remove_project_planet,
        name="remove_project_planet",
    ),
    path(
        "project-planet/<int:pk>/update-role/",
        views.update_project_planet_role,
        name="update_project_planet_role",
    ),
]
