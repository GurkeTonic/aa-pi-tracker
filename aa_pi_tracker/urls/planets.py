from django.urls import path

from .. import views

urlpatterns = [
    path("system-search/", views.system_search, name="system_search"),
    path("planet/<int:planet_pk>/optimizer.json", views.planet_optimizer_json, name="planet_optimizer_json"),
    path("planet/<int:planet_pk>/set-resource/", views.set_planet_resource, name="set_planet_resource"),
]
