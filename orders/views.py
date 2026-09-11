from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from restaurant.models import RestaurantProfile
from cart.utils import get_or_create_cart, get_cart_summary
from cart.models import CartItem
from menu.models import FoodItem
from payments.adapters import get_payment_adapter
from payments.models import Payment
from accounts.decorators import restaurant_admin_required
from .models import Order, OrderItem, Coupon
from .forms import CheckoutForm, QuickAddressForm


@login_required
def checkout_view(request):
    """
    Checkout workflow view:
      1. Validates active cart and kitchen open state
      2. Enforces minimum order amount
      3. Address selection (or instant in-line address creation)
      4. Modular payment method selection (COD, Online Mock, Razorpay)
      5. Order creation, immutable item snapshotting, and cart clearing
    """
    cart = get_or_create_cart(request)
    if not cart.items.exists():
        messages.warning(request, "Your super food cart is empty. Please add items to order.")
        return redirect('menu:food_list')

    summary = get_cart_summary(cart)
    profile = RestaurantProfile.get_instance()

    # Pre-condition: Kitchen accepting orders
    if not profile.is_accepting_orders:
        messages.error(request, "Our kitchen is currently paused. Please check back shortly.")
        return redirect('cart:cart_detail')

    # Pre-condition: Minimum order threshold
    if not summary['is_min_order_met']:
        messages.warning(
            request,
            f"Minimum order of ₹{summary['min_order_value']} required. Please add ₹{summary['min_order_shortfall']} more to proceed."
        )
        return redirect('cart:cart_detail')

    addresses = request.user.addresses.all()
    quick_addr_form = QuickAddressForm()

    # Handle In-line Address Addition from Checkout
    if request.method == 'POST' and request.POST.get('action') == 'add_address':
        quick_addr_form = QuickAddressForm(request.POST)
        if quick_addr_form.is_valid():
            new_addr = quick_addr_form.save(commit=False)
            new_addr.user = request.user
            if not addresses.exists():
                new_addr.is_default = True
            new_addr.save()
            messages.success(request, "Delivery address saved and selected.")
            return redirect('orders:checkout')

    # Handle Order Placement Submission
    if request.method == 'POST' and request.POST.get('action') != 'add_address':
        form = CheckoutForm(request.user, request.POST)
        if form.is_valid():
            address = form.cleaned_data['address']
            payment_method = form.cleaned_data['payment_method']
            customer_notes = form.cleaned_data['customer_notes']
            coupon_code = form.cleaned_data['coupon_code'].strip().upper()

            # Process Coupon Discount
            discount_amount = Decimal('0.00')
            coupon_obj = None
            if coupon_code:
                coupon_obj = Coupon.objects.filter(code__iexact=coupon_code).first()
                if coupon_obj:
                    is_valid, msg = coupon_obj.is_valid(summary['subtotal'])
                    if is_valid:
                        discount_amount = coupon_obj.calculate_discount(summary['subtotal'])
                    else:
                        messages.warning(request, f"Coupon '{coupon_code}' could not be applied: {msg}")

            # Recalculate Final Total with Discount
            final_total = max(
                Decimal('0.00'),
                summary['subtotal'] + summary['tax_amount'] + summary['delivery_fee'] - discount_amount
            )

            # Create Order Record with Address & Macro Snapshots
            order = Order.objects.create(
                customer=request.user,
                status=Order.Status.PENDING,
                delivery_name=address.contact_name or request.user.get_display_name(),
                delivery_phone=address.contact_phone or request.user.phone or '',
                delivery_address=address.full_address(),
                delivery_landmark=address.landmark,
                delivery_pincode=address.pincode,
                delivery_latitude=address.latitude,
                delivery_longitude=address.longitude,
                subtotal=summary['subtotal'],
                tax_amount=summary['tax_amount'],
                delivery_fee=summary['delivery_fee'],
                coupon=coupon_obj,
                coupon_code=coupon_code if coupon_obj else '',
                discount_amount=discount_amount,
                total_amount=final_total,
                total_calories=summary['total_calories'],
                total_protein=summary['total_protein'],
                customer_notes=customer_notes
            )

            # Snapshot Order Items
            for item in summary['items']:
                OrderItem.objects.create(
                    order=order,
                    food_item=item.food_item,
                    food_name=item.food_item.name,
                    food_type=item.food_item.food_type,
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                    subtotal=item.subtotal,
                    calories=item.total_calories,
                    protein_grams=item.total_protein,
                    customizations=item.customizations,
                    special_instructions=item.special_instructions
                )

            # Execute Modular Payment Adapter
            adapter = get_payment_adapter(payment_method)
            success, payment_record, redirect_info = adapter.process_payment(order, request)

            if success:
                # Advance order state to confirmed if payment succeeded or COD accepted
                if payment_record.is_paid():
                    order.transition_to(Order.Status.CONFIRMED)

                # Increment coupon usage
                if coupon_obj:
                    coupon_obj.used_count += 1
                    coupon_obj.save()

                # Clear Customer Cart
                cart.clear()

                messages.success(
                    request,
                    f"🎉 Order #{order.order_number} confirmed! Our kitchen has begun preparing your fresh super food."
                )
                return redirect('orders:order_success', order_number=order.order_number)
            else:
                messages.error(request, "Payment transaction could not be completed. Please try again.")
                return redirect('orders:checkout')
    else:
        form = CheckoutForm(request.user)

    context = {
        'form': form,
        'quick_addr_form': quick_addr_form,
        'summary': summary,
        'addresses': addresses,
        'profile': profile,
    }
    return render(request, 'orders/checkout.html', context)


@login_required
def order_success_view(request, order_number):
    """Post-checkout confirmation page showing order details and receipt."""
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    return render(request, 'orders/order_success.html', {'order': order})


@login_required
def order_list_view(request):
    """Customer's paginated order history with filter tabs."""
    tab = request.GET.get('tab', 'all')
    orders_qs = request.user.orders.prefetch_related('items').all()

    if tab == 'active':
        orders_qs = orders_qs.filter(status__in=[
            Order.Status.PENDING,
            Order.Status.CONFIRMED,
            Order.Status.PREPARING,
            Order.Status.READY_FOR_PICKUP,
            Order.Status.OUT_FOR_DELIVERY
        ])
    elif tab == 'completed':
        orders_qs = orders_qs.filter(status=Order.Status.DELIVERED)
    elif tab == 'cancelled':
        orders_qs = orders_qs.filter(status=Order.Status.CANCELLED)

    paginator = Paginator(orders_qs, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    active_count = request.user.orders.filter(status__in=[
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PREPARING,
        Order.Status.READY_FOR_PICKUP,
        Order.Status.OUT_FOR_DELIVERY
    ]).count()

    context = {
        'page_obj': page_obj,
        'active_tab': tab,
        'active_count': active_count,
        'total_orders_count': request.user.orders.count(),
    }
    return render(request, 'orders/order_list.html', context)


@login_required
def order_detail_view(request, order_number):
    """
    Detailed tracking view for customer order with OTP verification code & delivery status.
    """
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    delivery_assignment = getattr(order, 'delivery_assignment', None)
    
    context = {
        'order': order,
        'delivery_assignment': delivery_assignment,
    }
    return render(request, 'orders/order_detail.html', context)


@require_POST
@login_required
def customer_cancel_order_view(request, order_number):
    """
    Customer self-service cancellation:
    Allowed only while order status is PENDING (before kitchen starts prep).
    """
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    
    if order.status != Order.Status.PENDING:
        messages.error(request, "This order is already being prepared or dispatched and cannot be cancelled.")
        return redirect('orders:order_detail', order_number=order.order_number)

    reason = request.POST.get('reason', 'Customer requested cancellation')
    try:
        order.transition_to(Order.Status.CANCELLED, reason=reason)
        messages.info(request, f"Order #{order.order_number} has been cancelled.")
    except ValueError as e:
        messages.error(request, str(e))

    return redirect('orders:order_detail', order_number=order.order_number)


@require_POST
@login_required
def customer_reorder_view(request, order_number):
    """
    Quick Reorder action:
    Adds all available food items from a past order directly back into customer's active cart.
    """
    past_order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    cart = get_or_create_cart(request)
    added_count = 0

    for item in past_order.items.all():
        if item.food_item and item.food_item.is_available:
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                food_item=item.food_item,
                defaults={'quantity': item.quantity, 'special_instructions': item.special_instructions}
            )
            if not created:
                cart_item.quantity += item.quantity
                cart_item.save()
            added_count += 1

    if added_count > 0:
        messages.success(request, f"Added items from Order #{past_order.order_number} into your cart.")
        return redirect('cart:cart_detail')
    else:
        messages.warning(request, "Items from this past order are currently unavailable.")
        return redirect('orders:order_list')


# ==========================================
# State Machine Transitions & Live Tracking API
# ==========================================

@require_POST
@restaurant_admin_required
def order_status_update_view(request, order_number):
    """
    Kitchen Admin state machine transition endpoint.
    Transitions orders through PENDING -> CONFIRMED -> PREPARING -> READY_FOR_PICKUP -> OUT_FOR_DELIVERY -> DELIVERED.
    """
    order = get_object_or_404(Order, order_number=order_number)
    new_status = request.POST.get('status')
    reason = request.POST.get('reason', '')

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not new_status or not order.can_transition_to(new_status):
        err = f"Cannot transition order from {order.get_status_display()} to {new_status}."
        if is_ajax:
            return JsonResponse({'success': False, 'message': err}, status=400)
        messages.error(request, err)
        return redirect(request.META.get('HTTP_REFERER', 'restaurant:dashboard'))

    try:
        order.transition_to(new_status, reason=reason)
        
        # If order was delivered and payment was COD pending, mark payment completed
        if new_status == Order.Status.DELIVERED and hasattr(order, 'payment'):
            if order.payment.payment_method == Payment.Method.COD:
                order.payment.status = Payment.Status.SUCCESS
                order.payment.save()

        msg = f"Order #{order.order_number} updated to {order.get_status_display()}."
        if is_ajax:
            return JsonResponse({
                'success': True,
                'order_number': order.order_number,
                'status': order.status,
                'status_display': order.get_status_display(),
                'message': msg
            })
        messages.success(request, msg)
    except ValueError as e:
        if is_ajax:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
        messages.error(request, str(e))

    return redirect(request.META.get('HTTP_REFERER', 'restaurant:dashboard'))


def order_tracking_api_view(request, order_number):
    """
    Real-time polling endpoint for customer tracking page.
    Returns status progress, delivery assignment details, and OTP.
    """
    # Allow access to order owner, restaurant admin, or delivery partner
    order = get_object_or_404(Order, order_number=order_number)
    
    # Permission verification
    if not (request.user.is_authenticated and (
        request.user == order.customer or 
        request.user.is_restaurant_admin or 
        request.user.is_delivery_partner
    )):
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    assignment = getattr(order, 'delivery_assignment', None)
    partner_data = None
    if assignment:
        partner_data = {
            'name': assignment.delivery_partner.user.get_display_name(),
            'phone': assignment.delivery_partner.user.phone or '+91 7993476624',
            'vehicle_type': assignment.delivery_partner.get_vehicle_type_display(),
            'vehicle_number': assignment.delivery_partner.vehicle_number,
            'status': assignment.get_status_display(),
        }

    return JsonResponse({
        'order_number': order.order_number,
        'status': order.status,
        'status_display': order.get_status_display(),
        'is_completed': order.status == Order.Status.DELIVERED,
        'is_cancelled': order.status == Order.Status.CANCELLED,
        'cancellation_reason': order.cancellation_reason,
        'created_at': order.created_at.strftime('%I:%M %p') if order.created_at else None,
        'confirmed_at': order.confirmed_at.strftime('%I:%M %p') if order.confirmed_at else None,
        'prepared_at': order.prepared_at.strftime('%I:%M %p') if order.prepared_at else None,
        'picked_up_at': order.picked_up_at.strftime('%I:%M %p') if order.picked_up_at else None,
        'delivered_at': order.delivered_at.strftime('%I:%M %p') if order.delivered_at else None,
        'delivery_otp': assignment.delivery_otp if assignment else None,
        'partner': partner_data,
    })


@require_POST
@login_required
def apply_coupon_ajax(request):
    """
    AJAX endpoint to validate promo coupon and return calculated discount.
    """
    coupon_code = request.POST.get('coupon_code', '').strip().upper()
    cart = get_or_create_cart(request)
    summary = get_cart_summary(cart)

    if not coupon_code:
        return JsonResponse({'success': False, 'message': 'Please enter a coupon code.'}, status=400)

    coupon = Coupon.objects.filter(code__iexact=coupon_code).first()
    if not coupon:
        return JsonResponse({'success': False, 'message': 'Invalid coupon code.'}, status=404)

    is_valid, err_msg = coupon.is_valid(summary['subtotal'])
    if not is_valid:
        return JsonResponse({'success': False, 'message': err_msg}, status=400)

    discount = coupon.calculate_discount(summary['subtotal'])
    new_total = max(Decimal('0.00'), summary['total_amount'] - discount)

    return JsonResponse({
        'success': True,
        'coupon_code': coupon.code,
        'discount_amount': str(discount),
        'new_total': str(new_total),
        'message': f"Coupon '{coupon.code}' applied! You saved ₹{discount}."
    })
