from django import forms
from .models import Category, FoodItem


class CategoryForm(forms.ModelForm):
    """
    Form for adding and editing menu categories.
    """
    class Meta:
        model = Category
        fields = ('name', 'description', 'image', 'display_order', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name (e.g. High-Protein Bowls)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Brief description of category'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'display_order': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class FoodItemForm(forms.ModelForm):
    """
    Comprehensive food item creation and editing form with nutritional facts, meal slots, and badges.
    """
    available_slots = forms.MultipleChoiceField(
        choices=FoodItem.MealSlot.choices,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        initial=['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER']
    )

    class Meta:
        model = FoodItem
        fields = (
            'category',
            'name',
            'description',
            'food_type',
            'price',
            'discounted_price',
            'available_slots',
            'auto_timing_enabled',
            'calories',
            'protein_grams',
            'carbs_grams',
            'fats_grams',
            'fiber_grams',
            'is_high_protein',
            'is_calorie_conscious',
            'is_zero_preservative',
            'is_gluten_free',
            'is_keto_friendly',
            'is_chef_special',
            'is_bestseller',
            'is_available',
            'preparation_time_mins',
            'image'
        )
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dish Name (e.g. Mediterranean Quinoa Bowl)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full ingredients, dressing details, and health benefits'}),
            'food_type': forms.Select(attrs={'class': 'form-select'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '299.00'}),
            'discounted_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Optional sale price'}),
            
            # Nutrition Macros
            'calories': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 420'}),
            'protein_grams': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'e.g. 28.5'}),
            'carbs_grams': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'e.g. 45.0'}),
            'fats_grams': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'e.g. 12.0'}),
            'fiber_grams': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'e.g. 8.0'}),
            
            # Health & Operational Badges
            'is_high_protein': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_calorie_conscious': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_zero_preservative': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_gluten_free': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_keto_friendly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_chef_special': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_bestseller': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            'preparation_time_mins': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '20'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }
