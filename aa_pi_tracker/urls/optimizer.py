from django.urls import path

from .. import views

urlpatterns = [
    path("optimizer/analyze/", views.optimizer_analyze_json, name="optimizer_analyze_json"),
    path("optimizer/create-project/", views.optimizer_create_project, name="optimizer_create_project"),
    path("optimizer/create-corp-project/", views.optimizer_create_corp_project, name="optimizer_create_corp_project"),
    path("optimizer/save-home-system/", views.save_home_system, name="save_home_system"),
]
