import random
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from orders.models import Order


class DeliveryPartnerProfile(models.Model):
    """
    Profile for Nutrient fleet delivery partners.
    Tracks vehicle info, active availability, live location and total completed runs.
    """
    class VehicleType(models.TextChoices):
        MOTORCYCLE = 'MOTORCYCLE', _('Motorcycle / Bike')
        SCOOTER = 'SCOOTER', _('Scooter')
        EV_BIKE = 'EV_BIKE', _('Electric Scooter / EV')
        BICYCLE = 'BICYCLE', _('Bicycle')

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='delivery_profile'
    )
    vehicle_type = models.CharField(
        max_length=20,
        choices=VehicleType.choices,
        default=VehicleType.MOTORCYCLE
    )
    vehicle_number = models.CharField(
        max_length=30,
        help_text=_('e.g. TS 09 EA 1234')
    )
    driving_license_number = models.CharField(
        max_length=50,
        blank=True
    )
    is_available = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_('Online / Offline toggle for dispatching')
    )
    current_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    current_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True
    )
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('5.00')
    )
    total_deliveries = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Delivery Partner Profile')
        verbose_name_plural = _('Delivery Partner Profiles')

    def __str__(self):
        status = "Online" if self.is_available else "Offline"
        return f"{self.user.get_display_name()} ({self.vehicle_number}) - {status}"


class DeliveryAssignment(models.Model):
    """
    Mapping between an Order and the assigned Delivery Partner.
    Includes OTP verification for contact-free or verified handoff.
    """
    class AssignmentStatus(models.TextChoices):
        ASSIGNED = 'ASSIGNED', _('Assigned')
        ACCEPTED = 'ACCEPTED', _('Accepted by Partner')
        PICKED_UP = 'PICKED_UP', _('Picked Up from Kitchen')
        DELIVERED = 'DELIVERED', _('Delivered to Customer')
        REJECTED = 'REJECTED', _('Rejected / Reassigned')

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='delivery_assignment'
    )
    delivery_partner = models.ForeignKey(
        DeliveryPartnerProfile,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.ASSIGNED
    )
    delivery_otp = models.CharField(
        max_length=6,
        blank=True,
        help_text=_('4 or 6-digit OTP code to confirm delivery handoff')
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Delivery Assignment')
        verbose_name_plural = _('Delivery Assignments')

    def save(self, *args, **kwargs):
        if not self.delivery_otp:
            # Generate random 4-digit verification code
            self.delivery_otp = str(random.randint(1000, 9999))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Delivery #{self.order.order_number} -> {self.delivery_partner.user.get_display_name()} [{self.status}]"
