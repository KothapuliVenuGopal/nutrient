from django.urls import path
from . import views

app_name = 'menu'

urlpatterns = [
    # Customer-Facing Menu Routes
    path('', views.food_list, name='food_list'),
    path('item/<slug:slug>/', views.food_detail, name='food_detail'),
    path('item/<int:item_id>/customization-data/', views.food_item_customization_api, name='item_customization_api'),

    # Restaurant Admin - Category Management
    path('manage/categories/', views.admin_category_list, name='admin_category_list'),
    path('manage/categories/add/', views.admin_category_create, name='admin_category_create'),
    path('manage/categories/<int:pk>/edit/', views.admin_category_update, name='admin_category_update'),
    path('manage/categories/<int:pk>/delete/', views.admin_category_delete, name='admin_category_delete'),

    # Restaurant Admin - Food Item Management
    path('manage/items/', views.admin_food_list, name='admin_food_list'),
    path('manage/items/add/', views.admin_food_create, name='admin_food_create'),
    path('manage/items/quick-add/', views.admin_quick_food_create, name='admin_quick_food_create'),
    path('manage/items/<int:pk>/edit/', views.admin_food_update, name='admin_food_update'),
    path('manage/items/<int:pk>/delete/', views.admin_food_delete, name='admin_food_delete'),
    path('manage/items/<int:pk>/toggle-availability/', views.admin_food_toggle_availability, name='admin_food_toggle_availability'),
]
