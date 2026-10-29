from django.urls import path
from apps.quality import views

urlpatterns = [
    path('', views.quality_hub_view, name='quality_home'),
    path('samples/', views.quality_samples_view, name='quality_samples'),
    path('defects/', views.quality_defects_view, name='quality_defects'),
    path('giveaway/', views.quality_giveaway_view, name='quality_giveaway'),
    path('api/recalibrate/', views.quality_recalibrate_api, name='quality_recalibrate_api'),
    path('export/csv/', views.quality_export_csv, name='quality_export_csv'),
]

