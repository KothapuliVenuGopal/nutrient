from django.contrib import admin
from .models import DeliveryPartnerProfile, DeliveryAssignment


@admin.register(DeliveryPartnerProfile)
class DeliveryPartnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'vehicle_type', 'vehicle_number', 'is_available', 'rating', 'total_deliveries')
    list_filter = ('vehicle_type', 'is_available')
    search_fields = ('user__username', 'user__phone', 'vehicle_number')


@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = ('order', 'delivery_partner', 'status', 'delivery_otp', 'assigned_at', 'delivered_at')
    list_filter = ('status', 'assigned_at')
    search_fields = ('order__order_number', 'delivery_partner__user__username', 'delivery_otp')
