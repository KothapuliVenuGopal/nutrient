from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('accept/<int:assignment_id>/', views.accept_assignment_view, name='accept_assignment'),
    path('pickup/<int:assignment_id>/', views.pickup_assignment_view, name='pickup_assignment'),
    path('complete/<int:assignment_id>/', views.complete_delivery_view, name='complete_delivery'),
    path('toggle-availability/', views.toggle_availability_view, name='toggle_availability'),
]
