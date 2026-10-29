from django.urls import path
from . import views

urlpatterns = [
    path('products/', views.products_list_view, name='products_list'),
    path('products/add/', views.product_add_view, name='product_add'),
    path('products/<uuid:product_id>/edit/', views.product_edit_view, name='product_edit'),
    path('products/<uuid:product_id>/archive/', views.product_archive_view, name='product_archive'),
]
