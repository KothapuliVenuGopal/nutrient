"""
URL configuration for food_delivery project.
Nutrient – The Super Food (Single Restaurant Platform)
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('restaurant/', include('restaurant.urls')),
    path('delivery/', include('delivery.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
    path('subscriptions/', include('subscriptions.urls')),
    path('reviews/', include('reviews.urls')),
    path('', include('menu.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
