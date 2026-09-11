from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('submit/<slug:food_slug>/', views.submit_review_view, name='submit_review'),
    path('order/<str:order_number>/', views.submit_order_review_view, name='submit_order_review'),
    path('manage/', views.admin_reviews_view, name='admin_reviews'),
    path('manage/<int:review_id>/toggle/', views.toggle_review_approval_view, name='toggle_approval'),
]
