from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    raw_id_fields = ('food_item',)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'total_items', 'subtotal', 'updated_at')
    inlines = [CartItemInline]
    search_fields = ('user__username', 'session_key')


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'food_item', 'quantity', 'subtotal', 'created_at')
    raw_id_fields = ('cart', 'food_item')
