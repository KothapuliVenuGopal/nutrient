import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from menu.models import FoodItem


class Coupon(models.Model):
    """
    Promotional discounts and coupons for Nutrient customers (e.g. CLEAN20, HIGHPROTEIN).
    """
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'PERCENTAGE', _('Percentage (%)')
        FIXED = 'FIXED', _('Fixed Amount (₹)')

    code = models.CharField(
        max_length=30,
        unique=True,
        help_text=_('Unique coupon voucher code')
    )
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(
        max_length=15,
        choices=DiscountType.choices,
        default=DiscountType.PERCENTAGE
    )
    discount_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=_('Percentage off or flat rupee amount')
    )
    min_order_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Minimum order subtotal to qualify')
    )
    max_discount_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum discount cap for percentage offers')
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(
        default=500,
        help_text=_('Max global redemption limit')
    )
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Coupon')
        verbose_name_plural = _('Coupons')

    def is_valid(self, subtotal):
        now = timezone.now()
        if not self.is_active:
            return False, _("Coupon is no longer active.")
        if now < self.valid_from or now > self.valid_until:
            return False, _("Coupon has expired or is not yet active.")
        if self.used_count >= self.usage_limit:
            return False, _("Coupon usage limit has been reached.")
        if Decimal(str(subtotal)) < self.min_order_amount:
            return False, _(f"Minimum order of ₹{self.min_order_amount} required.")
        return True, ""

    def calculate_discount(self, subtotal):
        is_ok, msg = self.is_valid(subtotal)
        if not is_ok:
            return Decimal('0.00')
        subtotal_dec = Decimal(str(subtotal))
        if self.discount_type == self.DiscountType.PERCENTAGE:
            disc = (subtotal_dec * self.discount_value) / Decimal('100.00')
            if self.max_discount_amount:
                disc = min(disc, self.max_discount_amount)
            return disc.quantize(Decimal('0.01'))
        elif self.discount_type == self.DiscountType.FIXED:
            return min(self.discount_value, subtotal_dec).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()} - {self.discount_value})"


class Order(models.Model):
    """
    Customer Order for Nutrient – The Super Food.
    Implements a full state machine lifecycle for kitchen & delivery dispatch.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Order Placed')
        CONFIRMED = 'CONFIRMED', _('Confirmed by Kitchen')
        PREPARING = 'PREPARING', _('Preparing Your Meal')
        READY_FOR_PICKUP = 'READY_FOR_PICKUP', _('Ready for Pickup')
        OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', _('Out for Delivery')
        DELIVERED = 'DELIVERED', _('Delivered')
        CANCELLED = 'CANCELLED', _('Cancelled')

    order_number = models.CharField(
        max_length=32,
        unique=True,
        editable=False,
        db_index=True
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )

    # Immutable Delivery Snapshot (Protects history if customer updates Address book)
    delivery_name = models.CharField(max_length=100)
    delivery_phone = models.CharField(max_length=15)
    delivery_address = models.TextField(help_text=_('Complete street and locality address'))
    delivery_landmark = models.CharField(max_length=150, blank=True)
    delivery_pincode = models.CharField(max_length=10)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Financial Breakdown
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_orders'
    )
    coupon_code = models.CharField(max_length=30, blank=True)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Health & Nutrition Aggregate (Tracked for fitness conscious users)
    total_calories = models.PositiveIntegerField(default=0)
    total_protein = models.DecimalField(max_digits=6, decimal_places=1, default=Decimal('0.0'))

    # Notes & Operational details
    customer_notes = models.TextField(blank=True, help_text=_('Special delivery instructions'))
    cancellation_reason = models.TextField(blank=True)
    
    # State Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    prepared_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.order_number:
            date_str = timezone.now().strftime('%Y%m%d')
            unique_hex = uuid.uuid4().hex[:6].upper()
            self.order_number = f"NUT-{date_str}-{unique_hex}"
        super().save(*args, **kwargs)

    def can_transition_to(self, target_status):
        """Validates allowable transitions in order lifecycle state machine."""
        allowed_transitions = {
            self.Status.PENDING: [self.Status.CONFIRMED, self.Status.CANCELLED],
            self.Status.CONFIRMED: [self.Status.PREPARING, self.Status.CANCELLED],
            self.Status.PREPARING: [self.Status.READY_FOR_PICKUP, self.Status.CANCELLED],
            self.Status.READY_FOR_PICKUP: [self.Status.OUT_FOR_DELIVERY, self.Status.CANCELLED],
            self.Status.OUT_FOR_DELIVERY: [self.Status.DELIVERED, self.Status.CANCELLED],
            self.Status.DELIVERED: [],
            self.Status.CANCELLED: [],
        }
        return target_status in allowed_transitions.get(self.status, [])

    def transition_to(self, new_status, reason=''):
        """Executes a valid state change and records timestamp."""
        if not self.can_transition_to(new_status):
            raise ValueError(f"Illegal state transition from {self.status} to {new_status}")
        
        now = timezone.now()
        self.status = new_status
        if new_status == self.Status.CONFIRMED:
            self.confirmed_at = now
        elif new_status == self.Status.READY_FOR_PICKUP:
            self.prepared_at = now
        elif new_status == self.Status.OUT_FOR_DELIVERY:
            self.picked_up_at = now
        elif new_status == self.Status.DELIVERED:
            self.delivered_at = now
        elif new_status == self.Status.CANCELLED:
            self.cancellation_reason = reason
        self.save()

    def __str__(self):
        return f"{self.order_number} - {self.customer.get_display_name()} (₹{self.total_amount})"


class OrderItem(models.Model):
    """
    Individual item snapshot within an placed Order.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordered_instances'
    )
    food_name = models.CharField(max_length=150)
    food_type = models.CharField(max_length=15, default='VEG')
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Nutrition Snapshot per item
    calories = models.PositiveIntegerField(default=0)
    protein_grams = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'))
    customizations = models.JSONField(default=dict, blank=True)
    special_instructions = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _('Order Item')
        verbose_name_plural = _('Order Items')

    @property
    def customization_summary(self):
        """Returns list of formatted customization descriptions."""
        if not self.customizations or not isinstance(self.customizations, dict):
            return []
        lines = []
        for group, opts in self.customizations.get('selected_options', {}).items():
            if isinstance(opts, list) and opts:
                lines.append(f"{group}: {', '.join(opts)}")
            elif opts:
                lines.append(f"{group}: {opts}")
        return lines

    def save(self, *args, **kwargs):
        if not self.subtotal:
            self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.quantity}x {self.food_name} (Order {self.order.order_number})"
