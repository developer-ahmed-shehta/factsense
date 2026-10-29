from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('switch-role/', views.switch_role_view, name='switch_role'),
    path('quick-demo/<str:username>/', views.quick_demo_login_view, name='quick_demo_login'),
    path('set-language/', views.set_language_view, name='set_language'),
    path('role-landing/', views.role_landing_view, name='role_landing'),
]
