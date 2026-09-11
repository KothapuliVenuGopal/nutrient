from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from decimal import Decimal


class Category(models.Model):
    """
    Menu category (e.g., High-Protein Bowls, Gourmet Salads, Nourishing Soups, Cold-Pressed Drinks).
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True, help_text=_('Brief category description'))
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    display_order = models.PositiveIntegerField(default=0, help_text=_('Order of display in customer menu'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['display_order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class FoodItem(models.Model):
    """
    Food items served by Nutrient - The Super Food.
    Features detailed nutritional macros (Protein, Calories, Carbs, Fats) and dietary tags.
    """
    class FoodType(models.TextChoices):
        VEG = 'VEG', _('Vegetarian')
        NON_VEG = 'NON_VEG', _('Non-Vegetarian')
        VEGAN = 'VEGAN', _('Vegan')

    class MealSlot(models.TextChoices):
        BREAKFAST = 'BREAKFAST', _('Breakfast (07:00 AM – 11:30 AM)')
        LUNCH = 'LUNCH', _('Lunch (11:30 AM – 04:00 PM)')
        SNACK = 'SNACK', _('Snack (04:00 PM – 07:00 PM)')
        DINNER = 'DINNER', _('Dinner (07:00 PM – 11:00 PM)')
        ALL_DAY = 'ALL_DAY', _('All Day (07:00 AM – 11:00 PM)')

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='food_items'
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=170, unique=True, blank=True)
    description = models.TextField(help_text=_('Ingredients, preparation style and flavor profile'))
    food_type = models.CharField(
        max_length=10,
        choices=FoodType.choices,
        default=FoodType.VEG,
        db_index=True
    )

    # Pricing
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text=_('Regular Price in ₹')
    )
    discounted_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Optional discounted sale price in ₹')
    )

    # Nutritional Facts & Macros (Brand Core)
    calories = models.PositiveIntegerField(
        help_text=_('Energy in kcal'),
        default=350,
        db_index=True
    )
    protein_grams = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text=_('Protein in grams (g)'),
        default=Decimal('20.0'),
        db_index=True
    )
    carbs_grams = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text=_('Carbohydrates in grams (g)'),
        default=Decimal('35.0')
    )
    fats_grams = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text=_('Healthy Fats in grams (g)'),
        default=Decimal('10.0')
    )
    fiber_grams = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        help_text=_('Dietary Fiber in grams (g)'),
        default=Decimal('5.0')
    )

    # Health & Dietary Flags
    is_high_protein = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Mark if item provides high protein (e.g. >= 25g)')
    )
    is_calorie_conscious = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Mark if item is low-calorie / weight management friendly')
    )
    is_zero_preservative = models.BooleanField(
        default=True,
        help_text=_('100% clean ingredients, no artificial chemicals or preservatives')
    )
    is_gluten_free = models.BooleanField(default=False)
    is_keto_friendly = models.BooleanField(default=False)
    is_chef_special = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)

    # Operations & Inventory
    is_available = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_('Instant kitchen in-stock / out-of-stock toggle')
    )
    # Meal Timing & Automatic Availability
    available_slots = models.JSONField(
        default=list,
        blank=True,
        help_text=_("Active meal slots: ['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER'] or ['ALL_DAY']")
    )
    auto_timing_enabled = models.BooleanField(
        default=True,
        help_text=_('Automatically manage stock availability based on current meal timing')
    )
    preparation_time_mins = models.PositiveIntegerField(
        default=20,
        help_text=_('Estimated cooking/assembly time in minutes')
    )
    image = models.ImageField(upload_to='foods/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Food Item')
        verbose_name_plural = _('Food Items')
        ordering = ['-is_bestseller', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # Auto-tag high protein if >= 25g
        if self.protein_grams and self.protein_grams >= Decimal('25.0'):
            self.is_high_protein = True
        # Auto-tag calorie conscious if <= 400 kcal
        if self.calories and self.calories <= 400:
            self.is_calorie_conscious = True
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Returns discounted price if valid and less than original price, else regular price."""
        if self.discounted_price is not None and self.discounted_price > 0 and self.discounted_price < self.price:
            return self.discounted_price
        return self.price

    @property
    def discount_percentage(self):
        if self.discounted_price and self.discounted_price < self.price:
            discount = ((self.price - self.discounted_price) / self.price) * 100
            return int(round(discount))
        return 0

    @property
    def savings_amount(self):
        """Monetary savings in ₹ compared to original MRP."""
        if self.discounted_price and self.discounted_price < self.price:
            return (self.price - self.discounted_price).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def is_customizable(self):
        """Checks if item has customizable ingredient groups."""
        return self.customization_groups.filter(options__is_available=True).exists()

    def is_slot_active(self, current_time=None):
        """
        Determines whether the item is in active timing window based on IST time.
        Breakfast: 07:00 – 11:30 | Lunch: 11:30 – 16:00 | Snack: 16:00 – 19:00 | Dinner: 19:00 – 23:00
        """
        if not self.auto_timing_enabled:
            return True
        slots = self.available_slots or []
        if not slots or 'ALL_DAY' in slots:
            return True

        if current_time is None:
            from django.utils import timezone
            now = timezone.localtime()
            current_time = now.time()

        minutes = current_time.hour * 60 + current_time.minute
        slot_ranges = {
            'BREAKFAST': (420, 690),   # 07:00 AM - 11:30 AM
            'LUNCH': (690, 960),       # 11:30 AM - 04:00 PM
            'SNACK': (960, 1140),      # 04:00 PM - 07:00 PM
            'DINNER': (1140, 1380),    # 07:00 PM - 11:00 PM
        }

        for s in slots:
            rng = slot_ranges.get(s)
            if rng and rng[0] <= minutes < rng[1]:
                return True

        return False

    @property
    def is_orderable(self):
        """
        Item is orderable if manually marked In Stock AND (auto-timing is off OR currently within its meal timing slot).
        """
        if not self.is_available:
            return False
        return self.is_slot_active()

    @property
    def timing_badge_text(self):
        slots = self.available_slots or []
        if not slots or 'ALL_DAY' in slots:
            return "All Day (07:00 AM – 11:00 PM)"
        names = {
            'BREAKFAST': 'Breakfast (07:00-11:30 AM)',
            'LUNCH': 'Lunch (11:30 AM-04:00 PM)',
            'SNACK': 'Snack (04:00-07:00 PM)',
            'DINNER': 'Dinner (07:00-11:00 PM)',
        }
        return ", ".join([names.get(s, s) for s in slots])

    @property
    def current_status_badge(self):
        """Returns live operational status badge info."""
        if not self.is_available:
            return {'code': 'OUT_OF_STOCK', 'label': 'Sold Out', 'color': 'danger', 'icon': 'fa-ban'}
        if self.auto_timing_enabled and not self.is_slot_active():
            return {'code': 'TIMED_OUT', 'label': f'Available in {self.timing_badge_text}', 'color': 'secondary', 'icon': 'fa-clock'}
        return {'code': 'IN_STOCK', 'label': 'In Stock & Ready', 'color': 'success', 'icon': 'fa-check'}

    def __str__(self):
        return f"{self.name} (₹{self.effective_price})"


class CustomizationGroup(models.Model):
    """
    Logical grouping of bowl ingredients/customizations (e.g. Protein, Grains/Base, Veggies, Dressing, Super Drink).
    """
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.CASCADE,
        related_name='customization_groups'
    )
    name = models.CharField(max_length=100, help_text=_('e.g. Choose Your Protein, Choose Veggies, Choose Dressing'))
    min_choices = models.PositiveIntegerField(default=1, help_text=_('Minimum number of choices required'))
    max_choices = models.PositiveIntegerField(default=1, help_text=_('Maximum number of choices allowed'))
    is_required = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _('Customization Group')
        verbose_name_plural = _('Customization Groups')
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.food_item.name} - {self.name}"


class CustomizationOption(models.Model):
    """
    Individual selectable ingredient / option inside a group (e.g. Fresh Paneer, Soya Bean, Grilled Chicken, ABC Detox Elixir).
    """
    group = models.ForeignKey(
        CustomizationGroup,
        on_delete=models.CASCADE,
        related_name='options'
    )
    name = models.CharField(max_length=120)
    price_modifier = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text=_('Additional cost in ₹, if any')
    )
    calories_modifier = models.IntegerField(default=0, help_text=_('Calories +/-'))
    protein_modifier = models.DecimalField(max_digits=5, decimal_places=1, default=Decimal('0.0'), help_text=_('Protein +/- in grams'))
    is_available = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = _('Customization Option')
        verbose_name_plural = _('Customization Options')
        ordering = ['display_order', 'name']

    def __str__(self):
        return f"{self.name} ({self.group.name})"
