from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Address


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone', 'role', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'phone', 'first_name', 'last_name')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Nutrient Profile & Role', {'fields': ('role', 'phone', 'avatar')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Nutrient Profile & Role', {'fields': ('role', 'phone', 'email')}),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_type', 'street_address', 'city', 'pincode', 'is_default', 'created_at')
    list_filter = ('address_type', 'city', 'is_default')
    search_fields = ('user__username', 'street_address', 'landmark', 'pincode', 'contact_phone')
