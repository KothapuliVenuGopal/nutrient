import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from accounts.decorators import delivery_partner_required
from orders.models import Order
from payments.models import Payment
from .models import DeliveryPartnerProfile, DeliveryAssignment


@delivery_partner_required
def dashboard_view(request):
    """
    Rider Dashboard for Nutrient Delivery Fleet:
    - Availability status (Online/Offline)
    - Active assigned orders queue
    - One-click actions (Accept, Pick Up, Deliver with OTP)
    - Completed runs history and performance KPIs
    """
    profile, _ = DeliveryPartnerProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'vehicle_type': DeliveryPartnerProfile.VehicleType.MOTORCYCLE,
            'vehicle_number': 'TS09-EX-1001',
            'is_available': True
        }
    )

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Active assignments queue (Assigned, Accepted, Picked Up)
    active_assignments = DeliveryAssignment.objects.filter(
        delivery_partner=profile,
        status__in=[
            DeliveryAssignment.AssignmentStatus.ASSIGNED,
            DeliveryAssignment.AssignmentStatus.ACCEPTED,
            DeliveryAssignment.AssignmentStatus.PICKED_UP
        ]
    ).select_related('order__customer', 'order__payment').prefetch_related('order__items').order_by('assigned_at')

    # Completed runs history
    completed_assignments = DeliveryAssignment.objects.filter(
        delivery_partner=profile,
        status=DeliveryAssignment.AssignmentStatus.DELIVERED
    ).select_related('order__customer', 'order__payment').order_by('-delivered_at')[:15]

    # Performance KPIs
    today_completed_count = DeliveryAssignment.objects.filter(
        delivery_partner=profile,
        status=DeliveryAssignment.AssignmentStatus.DELIVERED,
        delivered_at__gte=today_start
    ).count()

    total_completed_count = profile.total_deliveries

    # Calculate estimated today's delivery earnings (₹40 per completed run)
    today_earnings = Decimal(str(today_completed_count * 40))

    context = {
        'profile': profile,
        'active_assignments': active_assignments,
        'completed_assignments': completed_assignments,
        'active_count': active_assignments.count(),
        'today_completed_count': today_completed_count,
        'total_completed_count': total_completed_count,
        'today_earnings': today_earnings,
    }
    return render(request, 'delivery/dashboard.html', context)


@require_POST
@delivery_partner_required
def toggle_availability_view(request):
    """
    Quick online/offline status switch for delivery partner.
    """
    profile, _ = DeliveryPartnerProfile.objects.get_or_create(user=request.user)
    profile.is_available = not profile.is_available
    profile.save()

    status_str = "Online (Ready for deliveries)" if profile.is_available else "Offline (On Break)"
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
        return JsonResponse({
            'success': True,
            'is_available': profile.is_available,
            'message': f"Status changed to {status_str}."
        })

    messages.info(request, f"You are now {status_str}.")
    return redirect('delivery:dashboard')


@require_POST
@delivery_partner_required
def accept_assignment_view(request, assignment_id):
    """
    Rider acknowledges and accepts delivery order task.
    """
    profile = get_object_or_404(DeliveryPartnerProfile, user=request.user)
    assignment = get_object_or_404(DeliveryAssignment, id=assignment_id, delivery_partner=profile)

    if assignment.status == DeliveryAssignment.AssignmentStatus.ASSIGNED:
        assignment.status = DeliveryAssignment.AssignmentStatus.ACCEPTED
        assignment.save()
        messages.success(request, f"Order #{assignment.order.order_number} accepted! Head to Nutrient kitchen.")
    else:
        messages.info(request, f"Order #{assignment.order.order_number} is already {assignment.get_status_display()}.")

    return redirect('delivery:dashboard')


@require_POST
@delivery_partner_required
def pickup_assignment_view(request, assignment_id):
    """
    Rider collects the food package from the kitchen and transitions order to OUT_FOR_DELIVERY.
    """
    profile = get_object_or_404(DeliveryPartnerProfile, user=request.user)
    assignment = get_object_or_404(DeliveryAssignment, id=assignment_id, delivery_partner=profile)
    order = assignment.order

    if assignment.status in [DeliveryAssignment.AssignmentStatus.ASSIGNED, DeliveryAssignment.AssignmentStatus.ACCEPTED]:
        assignment.status = DeliveryAssignment.AssignmentStatus.PICKED_UP
        assignment.picked_up_at = timezone.now()
        assignment.save()

        # Safely progress order to OUT_FOR_DELIVERY
        if order.status == Order.Status.READY_FOR_PICKUP:
            order.transition_to(Order.Status.OUT_FOR_DELIVERY)
        elif order.status == Order.Status.PREPARING:
            order.transition_to(Order.Status.READY_FOR_PICKUP)
            order.transition_to(Order.Status.OUT_FOR_DELIVERY)
        elif order.status == Order.Status.CONFIRMED:
            order.transition_to(Order.Status.PREPARING)
            order.transition_to(Order.Status.READY_FOR_PICKUP)
            order.transition_to(Order.Status.OUT_FOR_DELIVERY)

        messages.success(request, f"Order #{order.order_number} picked up! Safe riding to customer.")
    else:
        messages.info(request, f"Order #{order.order_number} is already picked up.")

    return redirect('delivery:dashboard')


@require_POST
@delivery_partner_required
def complete_delivery_view(request, assignment_id):
    """
    Verifies 4-digit customer delivery OTP and completes handoff:
    - Marks assignment DELIVERED
    - Marks order DELIVERED
    - Updates COD payment to SUCCESS if applicable
    - Increments rider total completed runs count
    """
    profile = get_object_or_404(DeliveryPartnerProfile, user=request.user)
    assignment = get_object_or_404(DeliveryAssignment, id=assignment_id, delivery_partner=profile)
    order = assignment.order

    entered_otp = request.POST.get('delivery_otp', '').strip()

    if not entered_otp:
        messages.error(request, "Please enter the 4-digit customer delivery OTP.")
        return redirect('delivery:dashboard')

    if entered_otp != assignment.delivery_otp.strip():
        messages.error(
            request,
            f"❌ Invalid OTP '{entered_otp}'! Please ask customer for the 4-digit code shown on their tracking screen."
        )
        return redirect('delivery:dashboard')

    # OTP Verified Successfully
    now = timezone.now()
    assignment.status = DeliveryAssignment.AssignmentStatus.DELIVERED
    assignment.delivered_at = now
    assignment.save()

    # Move order to DELIVERED
    if order.status == Order.Status.OUT_FOR_DELIVERY:
        order.transition_to(Order.Status.DELIVERED)
    elif order.can_transition_to(Order.Status.DELIVERED):
        order.transition_to(Order.Status.DELIVERED)

    # Increment rider delivery score
    profile.total_deliveries += 1
    profile.save()

    # Handle COD Cash collection
    if hasattr(order, 'payment') and order.payment.payment_method == Payment.Method.COD:
        order.payment.status = Payment.Status.SUCCESS
        order.payment.save()
        messages.success(
            request,
            f"🎉 Success! Order #{order.order_number} delivered. ₹{order.total_amount} COD cash marked as collected."
        )
    else:
        messages.success(
            request,
            f"🎉 Success! Order #{order.order_number} verified and marked as Delivered!"
        )

    return redirect('delivery:dashboard')
