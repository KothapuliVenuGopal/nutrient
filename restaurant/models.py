from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal


class RestaurantProfile(models.Model):
    """
    Singleton profile for 'Nutrient – The Super Food' (Single-restaurant platform).
    Contains core identity, kitchen controls, tax & delivery charge rules.
    """
    name = models.CharField(
        max_length=150,
        default='Nutrient – The Super Food',
        help_text=_('Official Restaurant Name')
    )
    tagline = models.CharField(
        max_length=255,
        default='Eat Clean. Stay Strong. Live Better.',
        help_text=_('Primary brand tagline')
    )
    secondary_tagline = models.CharField(
        max_length=255,
        default='Clean Food, Real Ingredients, Real Results',
        blank=True
    )
    description = models.TextField(
        default=(
            "Nutrient – The Super Food is dedicated to nourishing your body with high-protein bowls, "
            "fresh gourmet salads, nutritious warm soups, and cold-pressed drinks. "
            "100% clean, zero artificial preservatives, crafted fresh in Hyderabad."
        )
    )
    address_line = models.CharField(max_length=255, default="Madhapur / HITEC City")
    city = models.CharField(max_length=100, default="Hyderabad")
    state = models.CharField(max_length=100, default="Telangana")
    pincode = models.CharField(max_length=10, default="500081")
    phone = models.CharField(max_length=20, default="+91 7993476624")
    whatsapp_number = models.CharField(max_length=20, default="+91 7993476624")
    email = models.EmailField(default="contact@nutrientfood.in")
    
    logo = models.ImageField(upload_to='restaurant/', null=True, blank=True)
    banner_image = models.ImageField(upload_to='restaurant/', null=True, blank=True)

    # Kitchen Operations
    is_accepting_orders = models.BooleanField(
        default=True,
        help_text=_('Master switch: Toggle OFF during kitchen overload or maintenance.')
    )
    delivery_radius_km = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('15.00'),
        help_text=_('Max delivery radius from Hyderabad kitchen in KM')
    )
    avg_preparation_time_mins = models.PositiveIntegerField(
        default=25,
        help_text=_('Average kitchen preparation time in minutes')
    )

    # Billing & Financial Policies
    min_order_value = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('199.00'),
        help_text=_('Minimum order total before checkout is allowed')
    )
    default_delivery_charge = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('40.00'),
        help_text=_('Standard delivery fee (₹)')
    )
    free_delivery_threshold = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('500.00'),
        help_text=_('Orders above this amount get free delivery')
    )
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('5.00'),
        help_text=_('GST percentage applied to food subtotal (e.g. 5.00%)')
    )

    # Coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal('17.448294'))
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal('78.374184'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Restaurant Profile')
        verbose_name_plural = _('Restaurant Profile')

    def save(self, *args, **kwargs):
        # Enforce singleton pattern (only 1 restaurant record in table)
        if not self.pk and RestaurantProfile.objects.exists():
            self.pk = RestaurantProfile.objects.first().pk
        super().save(*args, **kwargs)

    @classmethod
    def get_instance(cls):
        profile, created = cls.objects.get_or_create(id=1)
        return profile

    def is_currently_open(self):
        """Checks if restaurant is accepting orders and within active operating hours."""
        if not self.is_accepting_orders:
            return False
        now = timezone.localtime()
        current_day = now.weekday()
        current_time = now.time()
        hours = self.business_hours.filter(day_of_week=current_day, is_closed=False).first()
        if not hours:
            return False
        return hours.opening_time <= current_time <= hours.closing_time

    def __str__(self):
        return self.name


class BusinessHour(models.Model):
    """
    Weekly operating hours for the restaurant.
    """
    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, _('Monday')
        TUESDAY = 1, _('Tuesday')
        WEDNESDAY = 2, _('Wednesday')
        THURSDAY = 3, _('Thursday')
        FRIDAY = 4, _('Friday')
        SATURDAY = 5, _('Saturday')
        SUNDAY = 6, _('Sunday')

    restaurant = models.ForeignKey(
        RestaurantProfile,
        on_delete=models.CASCADE,
        related_name='business_hours'
    )
    day_of_week = models.IntegerField(choices=DayOfWeek.choices)
    opening_time = models.TimeField(default='09:00:00')
    closing_time = models.TimeField(default='23:00:00')
    is_closed = models.BooleanField(default=False)

    class Meta:
        verbose_name = _('Business Hour')
        verbose_name_plural = _('Business Hours')
        unique_together = ('restaurant', 'day_of_week')
        ordering = ['day_of_week']

    def __str__(self):
        day_name = self.get_day_of_week_display()
        if self.is_closed:
            return f"{day_name}: Closed"
        return f"{day_name}: {self.opening_time.strftime('%I:%M %p')} - {self.closing_time.strftime('%I:%M %p')}"


class WhatsAppTemplate(models.Model):
    """
    Customizable WhatsApp notification message templates for customer engagement.
    Supports Customer Welcome, Order Status, and Daily Meal Broadcasts
    (Breakfast, Lunch, Evening Snack, Dinner) with dynamic merge tags.
    """
    class TemplateType(models.TextChoices):
        WELCOME_CATALOG = 'WELCOME_CATALOG', _('Customer Welcome & Menu Catalog')
        MEAL_BREAKFAST = 'MEAL_BREAKFAST', _('Daily Breakfast Alert')
        MEAL_LUNCH = 'MEAL_LUNCH', _('Daily Lunch Alert')
        MEAL_SNACK = 'MEAL_SNACK', _('Daily Evening Snack Alert')
        MEAL_DINNER = 'MEAL_DINNER', _('Daily Dinner Alert')
        ORDER_STATUS = 'ORDER_STATUS', _('Order Status Update')
        PROMOTIONAL = 'PROMOTIONAL', _('Promotional Broadcast')

    class TargetAudience(models.TextChoices):
        ALL = 'ALL', _('All Registered Customers')
        SUBSCRIBERS = 'SUBSCRIBERS', _('Active Subscribers Only')
        NON_SUBSCRIBERS = 'NON_SUBSCRIBERS', _('Non-Subscribers (Regular Diners) Only')
        VEG = 'VEG', _('Vegetarian Preference')
        NON_VEG = 'NON_VEG', _('Non-Vegetarian / High Protein')

    template_type = models.CharField(
        max_length=30,
        choices=TemplateType.choices,
        default=TemplateType.WELCOME_CATALOG,
        unique=True
    )
    title = models.CharField(max_length=150, default='Customer Welcome & Menu Highlights')
    body_text = models.TextField(
        default=(
            "🥗 *Welcome to Nutrient – The Super Food, {customer_name}!* 🌿\n"
            "Eat Clean. Stay Strong. Live Better.\n\n"
            "Thank you for joining us! We prepare fresh, 100% clean, high-protein meals in Hyderabad with zero preservatives.\n\n"
            "🍲 *TODAY'S SPECIAL SUPER FOOD MENU (30% OFF)*:\n"
            "{menu_items}\n\n"
            "📅 *WEEKLY & MONTHLY SUBSCRIPTIONS*:\n"
            "{subscription_plans}\n\n"
            "🛵 *Order Now with Free Delivery within 3km*:\n"
            "{order_link}\n\n"
            "💬 Kitchen Hotline & WhatsApp: {kitchen_phone}"
        )
    )
    scheduled_time = models.TimeField(
        null=True,
        blank=True,
        help_text=_('Scheduled daily dispatch time e.g. 07:30, 12:00, 16:30, 19:30')
    )
    target_audience = models.CharField(
        max_length=25,
        choices=TargetAudience.choices,
        default=TargetAudience.ALL,
        help_text=_('Filter recipient segment based on customer profile')
    )
    is_active = models.BooleanField(
        default=True,
        help_text=_('Master switch: Automatically send this message when triggered.')
    )
    include_live_menu = models.BooleanField(default=True)
    include_subscriptions = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('WhatsApp Template')
        verbose_name_plural = _('WhatsApp Templates')

    def __str__(self):
        return f"{self.title} ({'Active' if self.is_active else 'Disabled'})"

    @classmethod
    def get_welcome_template(cls):
        template, _ = cls.objects.get_or_create(
            template_type=cls.TemplateType.WELCOME_CATALOG,
            defaults={
                'title': 'Customer Welcome & Menu Highlights',
                'is_active': True,
                'include_live_menu': True,
                'include_subscriptions': True
            }
        )
        return template

    @classmethod
    def get_meal_template(cls, meal_slot: str):
        """
        Retrieves or initializes the designated template for a given daily meal session.
        meal_slot: 'BREAKFAST', 'LUNCH', 'SNACK', 'DINNER'
        """
        slot_upper = meal_slot.upper()
        mapping = {
            'BREAKFAST': (
                cls.TemplateType.MEAL_BREAKFAST,
                'Daily Breakfast Super Food Alert',
                '07:30:00',
                (
                    "🌅 *Good morning, {customer_name}!* 🌿\n"
                    "Fuel your morning with clean, energetic nutrition from *Nutrient – The Super Food*!\n\n"
                    "{subscription_status}\n\n"
                    "🍲 *TODAY'S MORNING SPECIALS (07:00 AM – 11:30 AM)*:\n"
                    "{available_dishes}\n\n"
                    "{recommended_bowl}\n\n"
                    "🛵 *Fresh Delivery to Your Doorstep*:\n"
                    "{order_link}\n\n"
                    "💬 Kitchen Hotline & WhatsApp: {kitchen_phone}"
                )
            ),
            'LUNCH': (
                cls.TemplateType.MEAL_LUNCH,
                'Daily Lunch Power Bowl Alert',
                '12:00:00',
                (
                    "☀️ *Lunchtime Power Boost, {customer_name}!* 🥗\n"
                    "Stay productive and nourished with today's 100% clean, high-protein lunch bowls.\n\n"
                    "{subscription_status}\n\n"
                    "🍲 *FRESH LUNCH BOWLS READY NOW (30% OFF)*:\n"
                    "{available_dishes}\n\n"
                    "{recommended_bowl}\n\n"
                    "🛵 *Order Now with Free 3km Delivery*:\n"
                    "{order_link}\n\n"
                    "💬 Kitchen Hotline & WhatsApp: {kitchen_phone}"
                )
            ),
            'SNACK': (
                cls.TemplateType.MEAL_SNACK,
                'Daily Evening Fitness Snack Alert',
                '16:30:00',
                (
                    "🥗 *Healthy Evening Snack Time, {customer_name}!* 🥜\n"
                    "Skip oily junk food and power up with our slow-roasted snacks and warm soups.\n\n"
                    "{subscription_status}\n\n"
                    "🍲 *TODAY'S CRUNCHY SNACKS & SOUPS (@ ₹119)*:\n"
                    "{available_dishes}\n\n"
                    "{recommended_bowl}\n\n"
                    "🛵 *Order Your Evening Energy Boost*:\n"
                    "{order_link}\n\n"
                    "💬 Kitchen Hotline & WhatsApp: {kitchen_phone}"
                )
            ),
            'DINNER': (
                cls.TemplateType.MEAL_DINNER,
                'Daily Clean Dinner Alert',
                '19:30:00',
                (
                    "🌙 *Good Evening, {customer_name}!* 🍲\n"
                    "End your day feeling light, strong, and deeply nourished with zero preservatives.\n\n"
                    "{subscription_status}\n\n"
                    "🍲 *TONIGHT'S SUPER FOOD DINNER (07:00 PM – 11:00 PM)*:\n"
                    "{available_dishes}\n\n"
                    "{recommended_bowl}\n\n"
                    "🛵 *Order Clean Dinner Before 11:00 PM*:\n"
                    "{order_link}\n\n"
                    "💬 Kitchen Hotline & WhatsApp: {kitchen_phone}"
                )
            ),
        }

        entry = mapping.get(slot_upper, mapping['LUNCH'])
        t_type, default_title, default_time, default_body = entry

        template, _ = cls.objects.get_or_create(
            template_type=t_type,
            defaults={
                'title': default_title,
                'scheduled_time': default_time,
                'body_text': default_body,
                'is_active': True,
                'include_live_menu': True,
                'include_subscriptions': False
            }
        )
        return template


class WhatsAppMessageLog(models.Model):
    """
    Audit log of all dispatched WhatsApp messages to customers.
    Includes delivery status, message type, and a 1-click WhatsApp Web preview link.
    """
    class Status(models.TextChoices):
        SENT = 'SENT', _('Sent / Dispatched')
        FAILED = 'FAILED', _('Failed')
        PENDING = 'PENDING', _('Pending')

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_logs'
    )
    recipient_phone = models.CharField(max_length=20)
    message_type = models.CharField(max_length=30, default='WELCOME', db_index=True)
    message_text = models.TextField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.SENT)
    sent_at = models.DateTimeField(auto_now_add=True)
    response_payload = models.TextField(blank=True)

    class Meta:
        verbose_name = _('WhatsApp Message Log')
        verbose_name_plural = _('WhatsApp Message Logs')
        ordering = ['-sent_at']

    @property
    def wa_web_link(self):
        from urllib.parse import quote
        import re
        clean_phone = re.sub(r'\D', '', self.recipient_phone)
        return f"https://api.whatsapp.com/send?phone={clean_phone}&text={quote(self.message_text)}"

    def __str__(self):
        return f"WhatsApp to {self.recipient_phone} ({self.status}) - {self.sent_at.strftime('%d %b, %H:%M')}"

