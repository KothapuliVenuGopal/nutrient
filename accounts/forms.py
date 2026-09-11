from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Address


class CustomerRegistrationForm(UserCreationForm):
    """
    Registration form for Nutrient customers with contact and profile fields.
    """
    first_name = forms.CharField(
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'})
    )
    phone = forms.CharField(
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 9876543210'})
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Choose username'})
        self.fields['username'].help_text = 'Letters, digits and @/./+/-/_ only.'
        for field in ['password1', 'password2']:
            if field in self.fields:
                self.fields[field].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter secure password'})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        # Basic cleanup: remove spaces and hyphens
        cleaned_phone = phone.replace(' ', '').replace('-', '')
        if User.objects.filter(phone=cleaned_phone).exists():
            raise forms.ValidationError('An account with this phone number already exists.')
        return cleaned_phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.CUSTOMER
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['phone']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """
    Bootstrap 5 styled login form supporting username/email authentication.
    """
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Username or Email',
            'autofocus': True
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )


class UserProfileForm(forms.ModelForm):
    """
    Form to update personal profile info, contact details and avatar.
    """
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'avatar')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 7993476624'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control'}),
        }


class AddressForm(forms.ModelForm):
    """
    Form for adding and editing customer delivery addresses.
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
            'address_type': forms.Select(attrs={'class': 'form-select'}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Recipient Name'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Number'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Road No, Street Name, Area'}),
            'apartment_flat': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Flat/House No, Building Name'}),
            'landmark': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nearby landmark'}),
            'city': forms.TextInput(attrs={'class': 'form-control', 'value': 'Hyderabad'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'value': 'Telangana'}),
            'pincode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 500081'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
