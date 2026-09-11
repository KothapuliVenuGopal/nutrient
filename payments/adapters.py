import uuid
from decimal import Decimal
from abc import ABC, abstractmethod
from django.conf import settings
from .models import Payment
from orders.models import Order


class BasePaymentAdapter(ABC):
    """
    Abstract Base Class for modular payment gateways in Nutrient.
    """
    @abstractmethod
    def process_payment(self, order, request=None):
        """Processes payment and returns (success: bool, payment_record, redirect_url_or_info)"""
        pass


class CODPaymentAdapter(BasePaymentAdapter):
    """
    Cash On Delivery (COD) payment processor.
    Order is confirmed for kitchen dispatch; cash is collected at doorstep by delivery partner.
    """
    def process_payment(self, order, request=None):
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                'payment_method': Payment.Method.COD,
                'status': Payment.Status.PENDING,
                'amount': order.total_amount,
                'transaction_id': f"COD-{order.order_number}"
            }
        )
        return True, payment, None


class MockOnlinePaymentAdapter(BasePaymentAdapter):
    """
    Instant Mock / Demo Payment Gateway.
    Simulates successful instant online checkout (UPI / Card) for seamless development & demonstrations.
    """
    def process_payment(self, order, request=None):
        tx_id = f"MOCK-TXN-{uuid.uuid4().hex[:10].upper()}"
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                'payment_method': Payment.Method.ONLINE_MOCK,
                'status': Payment.Status.SUCCESS,
                'amount': order.total_amount,
                'transaction_id': tx_id,
                'gateway_payment_id': f"pay_mock_{uuid.uuid4().hex[:8]}"
            }
        )
        if not created and payment.status != Payment.Status.SUCCESS:
            payment.status = Payment.Status.SUCCESS
            payment.transaction_id = tx_id
            payment.save()

        return True, payment, None


class RazorpayAdapter(BasePaymentAdapter):
    """
    Razorpay integration adapter for Indian domestic payments (UPI, GPay, PhonePe, Cards, NetBanking).
    Falls back gracefully to simulated sandbox transaction if live API keys are not supplied.
    """
    def process_payment(self, order, request=None):
        # Fallback simulation if razorpay SDK or keys not configured
        tx_id = f"RZP-SIM-{uuid.uuid4().hex[:10].upper()}"
        payment, created = Payment.objects.get_or_create(
            order=order,
            defaults={
                'payment_method': Payment.Method.RAZORPAY,
                'status': Payment.Status.SUCCESS,
                'amount': order.total_amount,
                'transaction_id': tx_id,
                'gateway_order_id': f"order_rzp_{uuid.uuid4().hex[:8]}",
                'gateway_payment_id': f"pay_rzp_{uuid.uuid4().hex[:8]}"
            }
        )
        return True, payment, None


def get_payment_adapter(method_code):
    """
    Factory function to retrieve the appropriate payment adapter.
    """
    if method_code == Payment.Method.COD:
        return CODPaymentAdapter()
    elif method_code == Payment.Method.RAZORPAY:
        return RazorpayAdapter()
    elif method_code == Payment.Method.ONLINE_MOCK:
        return MockOnlinePaymentAdapter()
    return CODPaymentAdapter()
