from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('success/<str:order_number>/', views.order_success_view, name='order_success'),
    path('tracking/<str:order_number>/', views.order_detail_view, name='order_detail'),
    path('cancel/<str:order_number>/', views.customer_cancel_order_view, name='customer_cancel_order'),
    path('reorder/<str:order_number>/', views.customer_reorder_view, name='customer_reorder'),
    path('apply-coupon/', views.apply_coupon_ajax, name='apply_coupon'),
    
    # State Machine & Live Tracking API
    path('manage/<str:order_number>/status/', views.order_status_update_view, name='order_status_update'),
    path('api/tracking/<str:order_number>/', views.order_tracking_api_view, name='order_tracking_api'),
    
    path('', views.order_list_view, name='order_list'),
]
