from django.contrib import admin
from .models import Order, OrderItem, Coupon


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('food_item', 'food_name', 'food_type', 'unit_price', 'quantity', 'subtotal', 'calories', 'protein_grams')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'status', 'total_amount', 'total_calories', 'total_protein', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order_number', 'customer__username', 'customer__email', 'delivery_phone')
    inlines = [OrderItemInline]
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'confirmed_at', 'prepared_at', 'picked_up_at', 'delivered_at')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'min_order_amount', 'max_discount_amount', 'usage_limit', 'used_count', 'is_active', 'valid_until')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code', 'description')
