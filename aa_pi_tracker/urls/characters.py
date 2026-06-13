from django.urls import path

from .. import views

urlpatterns = [
    path("add-character/", views.add_character, name="add_character"),
    path("remove-character/", views.remove_character, name="remove_character"),
    path("sync/", views.trigger_sync, name="trigger_sync"),
    path("sync-prices/", views.trigger_price_sync, name="trigger_price_sync"),
]
