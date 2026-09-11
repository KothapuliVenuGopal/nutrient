from django.contrib import admin
from .models import SubscriptionPlan, CustomerSubscription, DailySubscriptionDelivery


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'bowl_type', 'duration', 'total_bowls', 'original_price', 'price', 'discount_percentage', 'is_active')
    list_filter = ('bowl_type', 'duration', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


class DailyDeliveryInline(admin.TabularInline):
    model = DailySubscriptionDelivery
    extra = 0
    readonly_fields = ('delivery_date', 'time_slot', 'status', 'delivered_at')
    can_delete = False


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('subscription_number', 'user', 'plan', 'status', 'start_date', 'end_date', 'delivery_time_slot', 'bowls_delivered', 'bowls_total', 'is_paused')
    list_filter = ('status', 'delivery_time_slot', 'is_paused')
    search_fields = ('subscription_number', 'user__username', 'user__email', 'user__phone')
    inlines = [DailyDeliveryInline]


@admin.register(DailySubscriptionDelivery)
class DailySubscriptionDeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'subscription', 'delivery_date', 'time_slot', 'status', 'delivery_otp', 'delivered_at')
    list_filter = ('status', 'time_slot', 'delivery_date')
    search_fields = ('subscription__subscription_number', 'subscription__user__username')
