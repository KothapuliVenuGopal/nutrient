from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from menu.models import FoodItem
from orders.models import Order


class Review(models.Model):
    """
    Customer review and rating for dishes or overall meal experience.
    """
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    food_item = models.ForeignKey(
        FoodItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reviews',
        help_text=_('Item being reviewed (optional if reviewing overall order)')
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_reviews'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
        help_text=_('Rating scale from 1 (Poor) to 5 (Superb)')
    )
    comment = models.TextField(
        help_text=_('Customer feedback, taste notes, and experience')
    )
    is_approved = models.BooleanField(
        default=True,
        help_text=_('Moderation flag to control public visibility')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Review')
        verbose_name_plural = _('Reviews')
        ordering = ['-created_at']

    def __str__(self):
        target = self.food_item.name if self.food_item else f"Order #{self.order.order_number if self.order else ''}"
        return f"{self.rating}★ by {self.customer.get_display_name()} for {target}"
