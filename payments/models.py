from decimal import Decimal
from django.db import models
from django.utils.translation import gettext_lazy as _
from orders.models import Order


class Payment(models.Model):
    """
    Payment transaction record for an Order.
    Supports Cash on Delivery (COD) and Modular Online Gateway (Razorpay/Mock adapter).
    """
    class Method(models.TextChoices):
        COD = 'COD', _('Cash on Delivery')
        RAZORPAY = 'RAZORPAY', _('Razorpay (UPI, Cards, NetBanking)')
        ONLINE_MOCK = 'ONLINE_MOCK', _('Instant Demo / Mock Payment')

    class Status(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        PROCESSING = 'PROCESSING', _('Processing')
        SUCCESS = 'SUCCESS', _('Success')
        FAILED = 'FAILED', _('Failed')
        REFUNDED = 'REFUNDED', _('Refunded')

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='payment'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.COD,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    currency = models.CharField(max_length=5, default='INR')
    
    # Gateway specific metadata
    transaction_id = models.CharField(max_length=100, blank=True)
    gateway_order_id = models.CharField(max_length=100, blank=True)
    gateway_payment_id = models.CharField(max_length=100, blank=True)
    gateway_signature = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Payment')
        verbose_name_plural = _('Payments')
        ordering = ['-created_at']

    def is_paid(self):
        return self.status == self.Status.SUCCESS

    def __str__(self):
        return f"Payment #{self.id} for Order {self.order.order_number} - {self.get_status_display()} ({self.payment_method})"
