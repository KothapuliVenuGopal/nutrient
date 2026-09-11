from django import forms
from accounts.models import Address
from payments.models import Payment


class CheckoutForm(forms.Form):
    """
    Form for validating delivery address, payment method, notes and coupons during checkout.
    """
    address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        empty_label=None,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    payment_method = forms.ChoiceField(
        choices=Payment.Method.choices,
        initial=Payment.Method.COD,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    customer_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'e.g. Please do not ring bell, leave at security, extra cutlery'
        })
    )
    coupon_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter coupon code'
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].queryset = Address.objects.filter(user=user)
        # Select default address as initial if available
        default_addr = Address.objects.filter(user=user, is_default=True).first()
        if default_addr:
            self.fields['address'].initial = default_addr.id
        elif self.fields['address'].queryset.exists():
            self.fields['address'].initial = self.fields['address'].queryset.first().id


class QuickAddressForm(forms.ModelForm):
    """
    In-line address creation form for direct checkout use.
    """
    class Meta:
        model = Address
        fields = (
            'address_type',
            'contact_name',
            'contact_phone',
            'street_address',
            'apartment_flat',
            'landmark',
            'city',
            'state',
            'pincode',
            'is_default'
        )
        widgets = {
            'address_type': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Recipient Name'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Phone Number'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Street / Area'}),
            'apartment_flat': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Flat / House No'}),
            'landmark': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Landmark (optional)'}),
            'city': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'value': 'Hyderabad'}),
            'state': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'value': 'Telangana'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Pincode'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
