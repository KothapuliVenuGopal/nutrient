from django.urls import path
from . import views

app_name = 'restaurant'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('kitchen-orders/', views.kitchen_orders_view, name='kitchen_orders'),
    path('subscriptions/delivery/<int:delivery_id>/status/', views.update_subscription_delivery_status_view, name='subscription_delivery_status'),
    path('orders/<str:order_number>/assign-rider/', views.assign_rider_view, name='assign_rider'),
    path('toggle-orders/', views.toggle_accepting_orders_view, name='toggle_orders'),
    path('settings/', views.profile_settings_view, name='settings'),
    path('hours/', views.business_hours_view, name='hours'),
    path('whatsapp/', views.whatsapp_settings_view, name='whatsapp_settings'),
    path('whatsapp/test-send/', views.whatsapp_send_test_view, name='whatsapp_send_test'),
    path('whatsapp/meals/', views.meal_whatsapp_dashboard_view, name='meal_whatsapp_dashboard'),
    path('whatsapp/meals/<str:meal_slot>/edit/', views.meal_whatsapp_edit_view, name='meal_whatsapp_edit'),
    path('whatsapp/meals/<str:meal_slot>/broadcast/', views.meal_whatsapp_trigger_broadcast_view, name='meal_whatsapp_trigger_broadcast'),
    path('whatsapp/meals/<str:meal_slot>/test/', views.meal_whatsapp_test_send_view, name='meal_whatsapp_test_send'),
]
