from django import forms
from .models import RestaurantProfile, BusinessHour, WhatsAppTemplate


class RestaurantProfileForm(forms.ModelForm):
    """
    Form for updating single-restaurant settings, operational controls, and branding.
    """
    class Meta:
        model = RestaurantProfile
        fields = (
            'name',
            'tagline',
            'secondary_tagline',
            'description',
            'phone',
            'whatsapp_number',
            'email',
            'address_line',
            'city',
            'state',
            'pincode',
            'is_accepting_orders',
            'min_order_value',
            'default_delivery_charge',
            'free_delivery_threshold',
            'tax_percentage',
            'delivery_radius_km',
            'avg_preparation_time_mins',
            'logo',
            'banner_image'
        )
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'tagline': forms.TextInput(attrs={'class': 'form-control'}),
            'secondary_tagline': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'whatsapp_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address_line': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control'}),
            'is_accepting_orders': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'min_order_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'default_delivery_charge': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'free_delivery_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tax_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'delivery_radius_km': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1'}),
            'avg_preparation_time_mins': forms.NumberInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'banner_image': forms.FileInput(attrs={'class': 'form-control'}),
        }


class BusinessHourForm(forms.ModelForm):
    """
    Form for configuring individual day operating hours.
    """
    class Meta:
        model = BusinessHour
        fields = ('day_of_week', 'opening_time', 'closing_time', 'is_closed')
        widgets = {
            'day_of_week': forms.HiddenInput(),
            'opening_time': forms.TimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'time'}),
            'closing_time': forms.TimeInput(attrs={'class': 'form-control form-control-sm', 'type': 'time'}),
            'is_closed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class WhatsAppTemplateForm(forms.ModelForm):
    """
    Form for editing automated WhatsApp welcome message templates and dynamic tags.
    """
    class Meta:
        model = WhatsAppTemplate
        fields = ('title', 'is_active', 'include_live_menu', 'include_subscriptions', 'body_text')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_live_menu': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_subscriptions': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'body_text': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 12}),
        }


class WhatsAppMealTemplateForm(forms.ModelForm):
    """
    Form for editing scheduled daily meal WhatsApp broadcasts (Breakfast, Lunch, Snack, Dinner).
    """
    class Meta:
        model = WhatsAppTemplate
        fields = ('title', 'scheduled_time', 'target_audience', 'is_active', 'include_live_menu', 'body_text')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'scheduled_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'target_audience': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'include_live_menu': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'body_text': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 12}),
        }


