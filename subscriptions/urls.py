from django.urls import path
from . import views

app_name = 'subscriptions'

urlpatterns = [
    path('', views.subscription_plans_view, name='plans'),
    path('subscribe/<int:plan_id>/', views.subscribe_view, name='subscribe'),
    path('my/', views.my_subscriptions_view, name='my_subscriptions'),
    path('delivery/<int:delivery_id>/customize/', views.customize_daily_meal_ajax, name='customize_daily_meal'),
    path('<int:subscription_id>/toggle-pause/', views.toggle_pause_subscription_ajax, name='toggle_pause'),
]
