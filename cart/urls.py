from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail_view, name='cart_detail'),
    path('add/', views.cart_add_view, name='cart_add'),
    path('update/', views.cart_update_quantity_view, name='cart_update'),
    path('remove/<int:item_id>/', views.cart_remove_view, name='cart_remove'),
    path('clear/', views.cart_clear_view, name='cart_clear'),
    path('api/summary/', views.cart_api_summary, name='cart_api_summary'),
]
