from django.urls import path

from .. import views

urlpatterns = [
    path("project/<int:pk>/buildout/", views.buildout_page, name="buildout_page"),
    path("project/<int:pk>/maintenance/", views.maintenance_page, name="maintenance_page"),
    path("project/<int:pk>/maintenance/<int:char_pk>/", views.maintenance_char_page, name="maintenance_char_page"),
    path("project/<int:pk>/maintenance/<int:char_pk>/save/", views.maintenance_save_state, name="maintenance_save_state"),
]
