from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from menu.models import FoodItem
from decimal import Decimal


class Cart(models.Model):
    """
    Shopping cart supporting both authenticated users and guest sessions.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='carts'
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Session key for non-logged-in customers')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')

    @property
    def total_items(self):
        """Sum of quantities of all items in cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        """Total price before tax and delivery charges."""
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_calories(self):
        """Sum of calories across all ordered items."""
        return sum(item.total_calories for item in self.items.all())

    @property
    def total_protein(self):
        """Sum of protein grams across all ordered items."""
        return sum(item.total_protein for item in self.items.all())

    def clear(self):
        """Removes all items from the cart."""
        self.items.all().delete()

    def __str__(self):
        owner = self.user.username if self.user else f"Session: {self.session_key}"
        return f"Cart ({owner}) - {self.total_items} items"


class CartItem(models.Model):
    """
    Individual food item inside a customer's cart.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.CASCADE,
        related_name='cart_entries'
    )
    quantity = models.PositiveIntegerField(default=1)
    customizations = models.JSONField(default=dict, blank=True)
    customization_hash = models.CharField(max_length=64, default='', blank=True, db_index=True)
    special_instructions = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('e.g. Less spicy, dressing on the side, extra cutlery')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Cart Item')
        verbose_name_plural = _('Cart Items')
        unique_together = ('cart', 'food_item', 'customization_hash')

    @property
    def unit_price(self):
        base_price = self.food_item.effective_price
        if self.customizations and isinstance(self.customizations, dict):
            extra_price = Decimal(str(self.customizations.get('extra_price', 0.00)))
            return base_price + extra_price
        return base_price

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

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    @property
    def total_calories(self):
        extra_cal = 0
        if self.customizations and isinstance(self.customizations, dict):
            extra_cal = int(self.customizations.get('extra_calories', 0))
        return (self.food_item.calories + extra_cal) * self.quantity

    @property
    def total_protein(self):
        extra_prot = Decimal('0.0')
        if self.customizations and isinstance(self.customizations, dict):
            extra_prot = Decimal(str(self.customizations.get('extra_protein', 0.0)))
        return (self.food_item.protein_grams + extra_prot) * self.quantity

    def __str__(self):
        desc = f"{self.quantity}x {self.food_item.name}"
        if self.customization_hash:
            desc += " (Customized)"
        return desc
