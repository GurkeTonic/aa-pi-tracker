from django.urls import path

from .. import views

urlpatterns = [
    path("", views.index, name="index"),
    path("extractors/", views.extractors_page, name="extractors"),
    path("planets/", views.planets_page, name="planets"),
    path("projects/", views.projects_page, name="projects"),
    path("profit/", views.profit_page, name="profit"),
    path("characters/", views.characters_page, name="characters"),
    path("optimizer/", views.optimizer_page, name="optimizer"),
]
