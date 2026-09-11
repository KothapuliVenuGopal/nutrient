import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.utils.text import slugify
from accounts.models import Address


class SubscriptionPlan(models.Model):
    """
    Available weekly and monthly super food meal bowl subscription packages.
    """
    class BowlType(models.TextChoices):
        VEG_PROTEIN = 'VEG_PROTEIN', _('Veg Protein Bowl')
        NON_VEG_PROTEIN = 'NON_VEG_PROTEIN', _('Non-Veg Protein Bowl')
        VEG_MEAL = 'VEG_MEAL', _('Vegetable Meal Bowl')
        NON_VEG_MEAL = 'NON_VEG_MEAL', _('Non-Veg Meal Bowl')

    class Duration(models.TextChoices):
        WEEKLY = 'WEEKLY', _('Weekly (7 Bowls)')
        MONTHLY = 'MONTHLY', _('Monthly (30 Bowls)')

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    bowl_type = models.CharField(max_length=20, choices=BowlType.choices, db_index=True)
    duration = models.CharField(max_length=15, choices=Duration.choices, db_index=True)
    total_bowls = models.PositiveIntegerField(default=7, help_text=_('Total bowls included in cycle'))
    
    # Pricing (with 30% discount / 70% launch price)
    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_('Original MRP without discount in ₹')
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_('Discounted Subscriber Price in ₹ (70% of MRP)')
    )
    discount_percentage = models.PositiveIntegerField(default=30)
    
    description = models.TextField(help_text=_('Plan summary and inclusions'))
    perks = models.JSONField(
        default=list,
        blank=True,
        help_text=_('List of plan highlights e.g. Free 3km delivery, Dressing & Drink included')
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Subscription Plan')
        verbose_name_plural = _('Subscription Plans')
        ordering = ['display_order', 'bowl_type', 'duration']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.bowl_type}-{self.duration}")
        super().save(*args, **kwargs)

    @property
    def savings_amount(self):
        return (self.original_price - self.price).quantize(Decimal('0.01'))

    @property
    def price_per_bowl(self):
        if self.total_bowls:
            return (self.price / Decimal(str(self.total_bowls))).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def __str__(self):
        return f"{self.name} ({self.get_duration_display()} - ₹{self.price})"


class CustomerSubscription(models.Model):
    """
    An active, paused, or completed customer subscription.
    """
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', _('Active')
        PAUSED = 'PAUSED', _('Paused')
        COMPLETED = 'COMPLETED', _('Completed')
        CANCELLED = 'CANCELLED', _('Cancelled')

    class TimeSlot(models.TextChoices):
        LUNCH = 'LUNCH', _('Lunch (12:30 PM – 01:30 PM)')
        DINNER = 'DINNER', _('Dinner (07:30 PM – 08:30 PM)')

    subscription_number = models.CharField(max_length=32, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='meal_subscriptions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='customer_subscriptions'
    )
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True
    )
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField()
    delivery_time_slot = models.CharField(
        max_length=15,
        choices=TimeSlot.choices,
        default=TimeSlot.LUNCH
    )
    delivery_address = models.ForeignKey(
        Address,
        on_delete=models.PROTECT,
        related_name='subscription_deliveries'
    )
    bowls_total = models.PositiveIntegerField(default=7)
    bowls_delivered = models.PositiveIntegerField(default=0)
    
    # Customer's default recipe customization
    default_customization = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Default protein, base, veggies, dressing & drink preferences')
    )
    special_instructions = models.TextField(blank=True)
    is_paused = models.BooleanField(default=False)
    paused_at = models.DateTimeField(null=True, blank=True)
    payment_status = models.CharField(max_length=20, default='PAID')
    payment_method = models.CharField(max_length=20, default='ONLINE')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Customer Subscription')
        verbose_name_plural = _('Customer Subscriptions')
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.subscription_number:
            date_str = timezone.now().strftime('%Y%m%d')
            uid = uuid.uuid4().hex[:6].upper()
            self.subscription_number = f"SUB-{date_str}-{uid}"
        super().save(*args, **kwargs)

    @property
    def bowls_remaining(self):
        return max(0, self.bowls_total - self.bowls_delivered)

    @property
    def progress_percentage(self):
        if self.bowls_total:
            return int(round((self.bowls_delivered / self.bowls_total) * 100))
        return 0

    def toggle_pause(self):
        """Toggle pause/resume state."""
        if self.is_paused:
            self.is_paused = False
            self.status = self.Status.ACTIVE
            self.paused_at = None
        else:
            self.is_paused = True
            self.status = self.Status.PAUSED
            self.paused_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.subscription_number} - {self.user.get_display_name()} ({self.plan.name})"


class DailySubscriptionDelivery(models.Model):
    """
    Individual daily meal scheduled under an active subscription.
    """
    class Status(models.TextChoices):
        SCHEDULED = 'SCHEDULED', _('Scheduled')
        PREPARING = 'PREPARING', _('Preparing in Kitchen')
        OUT_FOR_DELIVERY = 'OUT_FOR_DELIVERY', _('Out for Delivery')
        DELIVERED = 'DELIVERED', _('Delivered')
        SKIPPED = 'SKIPPED', _('Skipped / Paused')

    subscription = models.ForeignKey(
        CustomerSubscription,
        on_delete=models.CASCADE,
        related_name='daily_deliveries'
    )
    delivery_date = models.DateField(db_index=True)
    time_slot = models.CharField(
        max_length=15,
        choices=CustomerSubscription.TimeSlot.choices,
        default=CustomerSubscription.TimeSlot.LUNCH
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True
    )
    customization = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Day-specific custom ingredients selected by customer')
    )
    delivery_notes = models.CharField(max_length=255, blank=True)
    delivery_otp = models.CharField(max_length=4, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Daily Subscription Delivery')
        verbose_name_plural = _('Daily Subscription Deliveries')
        ordering = ['delivery_date', 'time_slot']
        unique_together = ('subscription', 'delivery_date')

    @property
    def is_today(self):
        return self.delivery_date == timezone.localdate()

    @property
    def is_past(self):
        return self.delivery_date < timezone.localdate()

    @property
    def can_customize(self):
        return self.delivery_date >= timezone.localdate() and self.status == self.Status.SCHEDULED

    @property
    def active_customization(self):
        """Returns day-specific customization if provided, else falls back to subscription default."""
        if self.customization:
            return self.customization
        return self.subscription.default_customization

    @property
    def customization_summary(self):
        """Returns list of formatted customization descriptions."""
        cust = self.active_customization
        if not cust or not isinstance(cust, dict):
            return []
        lines = []
        options = cust.get('selected_options', {}) if 'selected_options' in cust else cust
        for group, opts in options.items():
            if group in ['extra_price', 'total_price']:
                continue
            if isinstance(opts, list) and opts:
                lines.append(f"{group}: {', '.join(opts)}")
            elif opts and isinstance(opts, str):
                lines.append(f"{group}: {opts}")
        return lines

    def __str__(self):
        return f"{self.subscription.subscription_number} - {self.delivery_date} ({self.status})"
