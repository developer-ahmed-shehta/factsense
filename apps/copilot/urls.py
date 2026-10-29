from django.urls import path
from . import views

urlpatterns = [
    path('', views.copilot_view, name='copilot_home'),
    path('api/chat/', views.copilot_chat_api, name='copilot_chat_api'),
    path('api/quick-summary/', views.copilot_quick_summary_api, name='copilot_quick_summary_api'),
]

