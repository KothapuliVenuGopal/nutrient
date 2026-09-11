from django.contrib import admin
from .models import RestaurantProfile, BusinessHour


class BusinessHourInline(admin.TabularInline):
    model = BusinessHour
    extra = 7
    max_num = 7


@admin.register(RestaurantProfile)
class RestaurantProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'city', 'is_accepting_orders', 'min_order_value', 'tax_percentage', 'default_delivery_charge')
    inlines = [BusinessHourInline]

    def has_add_permission(self, request):
        # Enforce singleton in admin: only allow adding if no record exists
        if RestaurantProfile.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(BusinessHour)
class BusinessHourAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'day_of_week', 'opening_time', 'closing_time', 'is_closed')
    list_filter = ('day_of_week', 'is_closed')
