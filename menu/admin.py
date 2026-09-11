from django.contrib import admin
from .models import Category, FoodItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'is_active', 'created_at')
    list_editable = ('display_order', 'is_active')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'food_type', 'price', 'discounted_price', 'calories', 'protein_grams', 'is_high_protein', 'is_available')
    list_filter = ('category', 'food_type', 'is_available', 'is_high_protein', 'is_calorie_conscious', 'is_bestseller')
    list_editable = ('price', 'discounted_price', 'is_available')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')
    fieldsets = (
        ('Basic Information', {'fields': ('category', 'name', 'slug', 'description', 'food_type', 'image')}),
        ('Pricing', {'fields': ('price', 'discounted_price')}),
        ('Nutritional Facts (Macros)', {'fields': ('calories', 'protein_grams', 'carbs_grams', 'fats_grams', 'fiber_grams')}),
        ('Badges & Operational Flags', {'fields': ('is_high_protein', 'is_calorie_conscious', 'is_zero_preservative', 'is_gluten_free', 'is_keto_friendly', 'is_bestseller', 'is_chef_special', 'is_available', 'preparation_time_mins')}),
    )
