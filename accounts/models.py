from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    Custom User model with role separation for Nutrient - The Super Food.
    Roles:
      - CUSTOMER: Standard ordering user
      - RESTAURANT_ADMIN: Kitchen manager & restaurant administrator
      - DELIVERY_PARTNER: Fleet delivery driver
    """
    class Role(models.TextChoices):
        CUSTOMER = 'CUSTOMER', _('Customer')
        RESTAURANT_ADMIN = 'RESTAURANT_ADMIN', _('Restaurant Admin')
        DELIVERY_PARTNER = 'DELIVERY_PARTNER', _('Delivery Partner')

    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
        help_text=_('User role in the delivery system')
    )
    phone = models.CharField(
        max_length=15,
        unique=True,
        null=True,
        blank=True,
        help_text=_('Mobile or WhatsApp number (e.g. +917993476624)')
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        help_text=_('Profile avatar photo')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_restaurant_admin(self):
        return self.role == self.Role.RESTAURANT_ADMIN or self.is_superuser

    @property
    def is_delivery_partner(self):
        return self.role == self.Role.DELIVERY_PARTNER

    def get_display_name(self):
        full_name = self.get_full_name().strip()
        return full_name if full_name else self.username

    def __str__(self):
        return f"{self.get_display_name()} ({self.get_role_display()})"


class Address(models.Model):
    """
    Customer delivery addresses. Multiple addresses allowed, one marked as default.
    """
    class AddressType(models.TextChoices):
        HOME = 'HOME', _('Home')
        WORK = 'WORK', _('Work / Office')
        OTHER = 'OTHER', _('Other')

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='addresses'
    )
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
        default=AddressType.HOME
    )
    contact_name = models.CharField(
        max_length=100,
        blank=True,
        help_text=_('Recipient contact person name')
    )
    contact_phone = models.CharField(
        max_length=15,
        blank=True,
        help_text=_('Phone number for delivery handover')
    )
    street_address = models.CharField(max_length=255)
    apartment_flat = models.CharField(max_length=100, blank=True)
    landmark = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100, default='Hyderabad')
    state = models.CharField(max_length=100, default='Telangana')
    pincode = models.CharField(max_length=10)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Delivery Address')
        verbose_name_plural = _('Delivery Addresses')
        ordering = ['-is_default', '-created_at']

    def save(self, *args, **kwargs):
        if self.is_default:
            Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def full_address(self):
        parts = [self.apartment_flat, self.street_address, self.landmark, self.city, f"{self.state} - {self.pincode}"]
        return ", ".join([p for p in parts if p])

    def __str__(self):
        return f"{self.get_address_type_display()}: {self.street_address}, {self.city}"


class PhoneOTP(models.Model):
    """
    Stores 6-digit One-Time Passwords for frictionless phone verification & login.
    Enforces expiry (10 mins) and maximum attempt limits (5 tries).
    """
    phone = models.CharField(max_length=15, db_index=True)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _('Phone OTP')
        verbose_name_plural = _('Phone OTPs')
        ordering = ['-created_at']

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.phone} - {'Verified' if self.is_verified else 'Pending'}"

