import json
from decimal import Decimal
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q
from django.views.decorators.http import require_POST
from accounts.decorators import restaurant_admin_required
from .models import RestaurantProfile, BusinessHour, WhatsAppTemplate, WhatsAppMessageLog
from .forms import RestaurantProfileForm, WhatsAppTemplateForm, WhatsAppMealTemplateForm
from .whatsapp_service import (
    build_welcome_whatsapp_message,
    dispatch_whatsapp_message,
    build_daily_meal_whatsapp_message,
    dispatch_meal_broadcast,
    get_customer_profile_data
)
from menu.models import FoodItem, Category
from orders.models import Order, OrderItem
from delivery.models import DeliveryPartnerProfile, DeliveryAssignment
from payments.models import Payment
from subscriptions.models import DailySubscriptionDelivery, CustomerSubscription
from accounts.models import User


@restaurant_admin_required
def dashboard_view(request):
    """
    Central Executive Kitchen Dashboard with Chart.js analytics, real-time KPI metrics,
    and kitchen order state-machine controls.
    """
    profile = RestaurantProfile.get_instance()
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Real-Time Status Counts
    all_orders = Order.objects.all()
    pending_orders_count = all_orders.filter(status=Order.Status.PENDING).count()
    confirmed_orders_count = all_orders.filter(status=Order.Status.CONFIRMED).count()
    preparing_orders_count = all_orders.filter(status=Order.Status.PREPARING).count()
    ready_orders_count = all_orders.filter(status=Order.Status.READY_FOR_PICKUP).count()
    out_for_delivery_count = all_orders.filter(status=Order.Status.OUT_FOR_DELIVERY).count()
    delivered_count = all_orders.filter(status=Order.Status.DELIVERED).count()

    # Active in-flight orders for the kitchen
    active_kitchen_orders = all_orders.filter(status__in=[
        Order.Status.PENDING,
        Order.Status.CONFIRMED,
        Order.Status.PREPARING,
        Order.Status.READY_FOR_PICKUP,
        Order.Status.OUT_FOR_DELIVERY
    ]).select_related('customer', 'delivery_assignment__delivery_partner__user').prefetch_related('items').order_by('created_at')

    # 2. Executive Financial KPIs
    today_orders = all_orders.filter(created_at__gte=today_start).exclude(status=Order.Status.CANCELLED)
    today_revenue = today_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    all_time_revenue = all_orders.filter(status=Order.Status.DELIVERED).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    
    aov_res = all_orders.exclude(status=Order.Status.CANCELLED).aggregate(Avg('total_amount'))['total_amount__avg']
    average_order_value = Decimal(str(round(aov_res, 2))) if aov_res else Decimal('0.00')

    # Menu inventory stats
    total_food_items = FoodItem.objects.count()
    out_of_stock_count = FoodItem.objects.filter(is_available=False).count()
    categories_count = Category.objects.count()

    # Available Delivery Partners for dispatching
    available_riders = DeliveryPartnerProfile.objects.filter(is_available=True).select_related('user')

    # 3. Chart.js Data: 7-Day Revenue & Orders Trend
    days_labels = []
    revenue_data = []
    order_counts_data = []

    for i in range(6, -1, -1):
        target_date = (now - timedelta(days=i)).date()
        days_labels.append(target_date.strftime('%b %d'))

        day_orders = all_orders.filter(
            created_at__date=target_date
        ).exclude(status=Order.Status.CANCELLED)

        day_rev = day_orders.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        revenue_data.append(float(day_rev))
        order_counts_data.append(day_orders.count())

    # 4. Chart.js Data: Order Status Distribution
    status_distribution = {
        'Delivered': delivered_count,
        'Active Prep': confirmed_orders_count + preparing_orders_count,
        'Dispatched': out_for_delivery_count,
        'Pending': pending_orders_count,
        'Cancelled': all_orders.filter(status=Order.Status.CANCELLED).count(),
    }

    # 5. Chart.js Data: Top 5 Bestselling Super Foods
    top_dishes = OrderItem.objects.values('food_name').annotate(
        total_quantity=Sum('quantity')
    ).order_by('-total_quantity')[:5]

    top_dish_names = [d['food_name'] for d in top_dishes]
    top_dish_quantities = [d['total_quantity'] for d in top_dishes]

    context = {
        'profile': profile,
        'today_revenue': today_revenue,
        'all_time_revenue': all_time_revenue,
        'average_order_value': average_order_value,
        'pending_orders_count': pending_orders_count,
        'confirmed_orders_count': confirmed_orders_count,
        'preparing_orders_count': preparing_orders_count,
        'ready_orders_count': ready_orders_count,
        'out_for_delivery_count': out_for_delivery_count,
        'delivered_count': delivered_count,
        'active_kitchen_orders': active_kitchen_orders,
        'total_food_items': total_food_items,
        'out_of_stock_count': out_of_stock_count,
        'categories_count': categories_count,
        'available_riders': available_riders,
        # Chart.js Serialized Data
        'chart_days_labels': json.dumps(days_labels),
        'chart_revenue_data': json.dumps(revenue_data),
        'chart_orders_data': json.dumps(order_counts_data),
        'chart_status_labels': json.dumps(list(status_distribution.keys())),
        'chart_status_data': json.dumps(list(status_distribution.values())),
        'chart_top_dish_names': json.dumps(top_dish_names),
        'chart_top_dish_quantities': json.dumps(top_dish_quantities),
    }
    return render(request, 'restaurant/dashboard.html', context)


@require_POST
@restaurant_admin_required
def assign_rider_view(request, order_number):
    """
    Assigns an available delivery partner to an order and moves status to OUT_FOR_DELIVERY.
    """
    order = get_object_or_404(Order, order_number=order_number)
    rider_id = request.POST.get('rider_id')

    if not rider_id:
        messages.error(request, "Please select a delivery partner.")
        return redirect('restaurant:dashboard')

    rider = get_object_or_404(DeliveryPartnerProfile, id=rider_id)

    assignment, created = DeliveryAssignment.objects.get_or_create(
        order=order,
        defaults={'delivery_partner': rider, 'status': DeliveryAssignment.AssignmentStatus.ASSIGNED}
    )
    if not created:
        assignment.delivery_partner = rider
        assignment.status = DeliveryAssignment.AssignmentStatus.ASSIGNED
        assignment.save()

    # Advance order to OUT_FOR_DELIVERY if in READY_FOR_PICKUP or PREPARING
    if order.status == Order.Status.READY_FOR_PICKUP:
        order.transition_to(Order.Status.OUT_FOR_DELIVERY)
    elif order.status == Order.Status.PREPARING:
        order.transition_to(Order.Status.READY_FOR_PICKUP)
        order.transition_to(Order.Status.OUT_FOR_DELIVERY)

    messages.success(
        request,
        f"Order #{order.order_number} assigned to rider {rider.user.get_display_name()} (OTP: {assignment.delivery_otp})."
    )
    return redirect('restaurant:dashboard')


@restaurant_admin_required
def kitchen_orders_view(request):
    """
    Full dedicated Kitchen Display System (KDS) screen showing live queue of orders.
    """
    status_filter = request.GET.get('status', 'active')
    orders = Order.objects.select_related('customer', 'delivery_assignment__delivery_partner__user').prefetch_related('items').all()

    if status_filter == 'active':
        orders = orders.filter(status__in=[
            Order.Status.PENDING,
            Order.Status.CONFIRMED,
            Order.Status.PREPARING,
            Order.Status.READY_FOR_PICKUP,
            Order.Status.OUT_FOR_DELIVERY
        ]).order_by('created_at')
    elif status_filter != 'all':
        orders = orders.filter(status=status_filter).order_by('-created_at')
    else:
        orders = orders.order_by('-created_at')

    available_riders = DeliveryPartnerProfile.objects.filter(is_available=True).select_related('user')

    today_date = timezone.localdate()
    today_subscriptions = DailySubscriptionDelivery.objects.filter(
        delivery_date=today_date
    ).select_related(
        'subscription__user',
        'subscription__plan',
        'subscription__delivery_address'
    ).order_by('time_slot')

    context = {
        'orders': orders,
        'status_filter': status_filter,
        'available_riders': available_riders,
        'statuses': Order.Status.choices,
        'today_subscriptions': today_subscriptions,
        'today_date': today_date,
    }
    return render(request, 'restaurant/kitchen_orders.html', context)


@require_POST
@restaurant_admin_required
def update_subscription_delivery_status_view(request, delivery_id):
    """
    Updates status of a daily subscription meal delivery from KDS (SCHEDULED -> PREPARING -> OUT_FOR_DELIVERY -> DELIVERED).
    """
    delivery = get_object_or_404(DailySubscriptionDelivery, id=delivery_id)
    new_status = request.POST.get('status')
    if new_status in DailySubscriptionDelivery.Status.values:
        delivery.status = new_status
        if new_status == DailySubscriptionDelivery.Status.DELIVERED:
            delivery.delivered_at = timezone.now()
            sub = delivery.subscription
            sub.bowls_delivered = DailySubscriptionDelivery.objects.filter(
                subscription=sub, status=DailySubscriptionDelivery.Status.DELIVERED
            ).count()
            if sub.bowls_delivered >= sub.bowls_total:
                sub.status = sub.Status.COMPLETED
            sub.save()
        delivery.save()
        messages.success(request, f"Subscription #{delivery.subscription.subscription_number} delivery updated to {delivery.get_status_display()}.")
    return redirect('restaurant:kitchen_orders')


@restaurant_admin_required
def toggle_accepting_orders_view(request):
    """
    Quick master switch to accept or pause incoming orders.
    """
    if request.method == 'POST':
        profile = RestaurantProfile.get_instance()
        profile.is_accepting_orders = not profile.is_accepting_orders
        profile.save()
        
        status_text = "now accepting orders" if profile.is_accepting_orders else "orders are now PAUSED"
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
            return JsonResponse({
                'success': True,
                'is_accepting_orders': profile.is_accepting_orders,
                'message': f"Kitchen {status_text}."
            })
        
        messages.success(request, f"Kitchen status updated: {status_text}.")
        return redirect('restaurant:dashboard')
    return redirect('restaurant:dashboard')


@restaurant_admin_required
def profile_settings_view(request):
    """
    Configuration editor for single-restaurant operational rules and branding.
    """
    profile = RestaurantProfile.get_instance()
    if request.method == 'POST':
        form = RestaurantProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Restaurant profile and operational settings saved.")
            return redirect('restaurant:settings')
    else:
        form = RestaurantProfileForm(instance=profile)

    return render(request, 'restaurant/profile_settings.html', {'form': form, 'profile': profile})


@restaurant_admin_required
def business_hours_view(request):
    """
    Weekly operating hours schedule editor.
    """
    profile = RestaurantProfile.get_instance()
    
    for day_val in BusinessHour.DayOfWeek.values:
        BusinessHour.objects.get_or_create(
            restaurant=profile,
            day_of_week=day_val,
            defaults={'opening_time': '09:00:00', 'closing_time': '23:00:00', 'is_closed': False}
        )
    
    hours = BusinessHour.objects.filter(restaurant=profile).order_by('day_of_week')
    
    if request.method == 'POST':
        for hour in hours:
            prefix = f"day_{hour.day_of_week}_"
            opening = request.POST.get(f"{prefix}opening_time")
            closing = request.POST.get(f"{prefix}closing_time")
            is_closed = request.POST.get(f"{prefix}is_closed") == 'on'
            
            if opening:
                hour.opening_time = opening
            if closing:
                hour.closing_time = closing
            hour.is_closed = is_closed
            hour.save()
            
        messages.success(request, "Weekly business hours updated successfully.")
        return redirect('restaurant:hours')

    return render(request, 'restaurant/business_hours.html', {'profile': profile, 'hours': hours})


@restaurant_admin_required
def whatsapp_settings_view(request):
    """
    Admin control panel to customize WhatsApp automated welcome messages,
    configure live menu / subscription inclusion switches, preview generated messages,
    and view historical dispatch audit logs.
    """
    profile = RestaurantProfile.get_instance()
    template = WhatsAppTemplate.get_welcome_template()

    if request.method == 'POST':
        form = WhatsAppTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "WhatsApp notification template saved successfully!")
            return redirect('restaurant:whatsapp_settings')
    else:
        form = WhatsAppTemplateForm(instance=template)

    base_url = request.build_absolute_uri('/menu/')
    live_preview = build_welcome_whatsapp_message(request.user, template=template, base_url=base_url)

    logs = WhatsAppMessageLog.objects.select_related('customer').order_by('-sent_at')[:50]
    total_dispatched = WhatsAppMessageLog.objects.count()

    context = {
        'profile': profile,
        'template': template,
        'form': form,
        'live_preview': live_preview,
        'logs': logs,
        'total_dispatched': total_dispatched,
    }
    return render(request, 'restaurant/whatsapp_settings.html', context)


@restaurant_admin_required
@require_POST
def whatsapp_send_test_view(request):
    """
    Sends a test WhatsApp message to any specified phone number for instant verification.
    """
    recipient_phone = request.POST.get('recipient_phone', '').strip()
    if not recipient_phone:
        messages.error(request, "Please enter a valid recipient mobile number.")
        return redirect('restaurant:whatsapp_settings')

    base_url = request.build_absolute_uri('/menu/')
    message_text = build_welcome_whatsapp_message(request.user, base_url=base_url)

    log_entry = dispatch_whatsapp_message(recipient_phone, message_text, customer=request.user)

    messages.success(
        request,
        f"Test WhatsApp message generated for {recipient_phone}! You can preview or send it via WhatsApp Web."
    )
    return redirect('restaurant:whatsapp_settings')


@restaurant_admin_required
def meal_whatsapp_dashboard_view(request):
    """
    Control hub for scheduled & manual daily meal WhatsApp broadcasts
    (Breakfast, Lunch, Evening Snack, Dinner) with customer personalization and audience targeting.
    """
    profile = RestaurantProfile.get_instance()
    slots = ['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER']
    slot_meta = {
        'BREAKFAST': {'label': 'Morning Breakfast', 'icon': 'fa-sun', 'color': 'warning', 'time_window': '07:00 AM – 11:30 AM'},
        'LUNCH': {'label': 'Power Lunch', 'icon': 'fa-bowl-food', 'color': 'success', 'time_window': '11:30 AM – 04:00 PM'},
        'SNACK': {'label': 'Evening Fitness Snack', 'icon': 'fa-apple-whole', 'color': 'info', 'time_window': '04:00 PM – 07:00 PM'},
        'DINNER': {'label': 'Clean Dinner', 'icon': 'fa-moon', 'color': 'primary', 'time_window': '07:00 PM – 11:00 PM'},
    }

    base_url = request.build_absolute_uri('/')
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # Global customer metrics
    all_customers = User.objects.filter(role=User.Role.CUSTOMER).exclude(phone__isnull=True).exclude(phone='')
    total_customers_count = all_customers.count()
    active_subscribers_count = CustomerSubscription.objects.filter(status=CustomerSubscription.Status.ACTIVE).values('user_id').distinct().count()

    meal_cards = []
    for s in slots:
        tmpl = WhatsAppTemplate.get_meal_template(s)
        preview_text = build_daily_meal_whatsapp_message(request.user, s, template=tmpl, base_url=base_url)

        # Count sent today
        sent_today_count = WhatsAppMessageLog.objects.filter(
            message_type=f"MEAL_{s}",
            sent_at__gte=today_start
        ).count()

        # Compute eligible audience count
        if tmpl.target_audience == 'SUBSCRIBERS':
            audience_count = active_subscribers_count
        elif tmpl.target_audience == 'NON_SUBSCRIBERS':
            audience_count = max(0, total_customers_count - active_subscribers_count)
        else:
            audience_count = total_customers_count

        meal_cards.append({
            'slot': s,
            'meta': slot_meta[s],
            'template': tmpl,
            'preview_text': preview_text,
            'sent_today_count': sent_today_count,
            'audience_count': audience_count,
        })

    # Recent 50 meal broadcast logs
    logs = WhatsAppMessageLog.objects.filter(
        message_type__startswith='MEAL_'
    ).select_related('customer').order_by('-sent_at')[:50]
    total_meal_broadcasts = WhatsAppMessageLog.objects.filter(message_type__startswith='MEAL_').count()

    context = {
        'profile': profile,
        'meal_cards': meal_cards,
        'total_customers_count': total_customers_count,
        'active_subscribers_count': active_subscribers_count,
        'total_meal_broadcasts': total_meal_broadcasts,
        'logs': logs,
    }
    return render(request, 'restaurant/whatsapp_meal_dashboard.html', context)


@restaurant_admin_required
def meal_whatsapp_edit_view(request, meal_slot):
    """
    Editor for specific meal session WhatsApp templates and timing settings.
    """
    profile = RestaurantProfile.get_instance()
    slot_upper = meal_slot.upper()
    template = WhatsAppTemplate.get_meal_template(slot_upper)

    if request.method == 'POST':
        form = WhatsAppMealTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, f"WhatsApp {slot_upper} alert template updated successfully!")
            return redirect('restaurant:meal_whatsapp_dashboard')
    else:
        form = WhatsAppMealTemplateForm(instance=template)

    base_url = request.build_absolute_uri('/')
    live_preview = build_daily_meal_whatsapp_message(request.user, slot_upper, template=template, base_url=base_url)

    context = {
        'profile': profile,
        'slot': slot_upper,
        'template': template,
        'form': form,
        'live_preview': live_preview,
    }
    return render(request, 'restaurant/whatsapp_meal_edit.html', context)


@restaurant_admin_required
@require_POST
def meal_whatsapp_trigger_broadcast_view(request, meal_slot):
    """
    1-Click manual execution to dispatch the meal notification to eligible customers.
    """
    slot_upper = meal_slot.upper()
    template = WhatsAppTemplate.get_meal_template(slot_upper)
    audience = request.POST.get('audience') or template.target_audience
    base_url = request.build_absolute_uri('/')

    res = dispatch_meal_broadcast(meal_slot=slot_upper, audience=audience, base_url=base_url)

    if res.get('status') == 'paused':
        messages.warning(request, res['message'])
    else:
        messages.success(
            request,
            f"🚀 {slot_upper} broadcast completed! Sent: {res['dispatched_count']} | Skipped: {res['skipped_count']} (already received today)."
        )

    return redirect('restaurant:meal_whatsapp_dashboard')


@restaurant_admin_required
@require_POST
def meal_whatsapp_test_send_view(request, meal_slot):
    """
    Sends an immediate test WhatsApp message for a specific meal slot to any given phone number.
    """
    slot_upper = meal_slot.upper()
    recipient_phone = request.POST.get('recipient_phone', '').strip()
    if not recipient_phone:
        messages.error(request, "Please enter a valid recipient phone number.")
        return redirect('restaurant:meal_whatsapp_dashboard')

    base_url = request.build_absolute_uri('/')
    message_text = build_daily_meal_whatsapp_message(request.user, slot_upper, base_url=base_url)

    log_entry = dispatch_whatsapp_message(
        recipient_phone,
        message_text,
        customer=request.user,
        message_type=f"TEST_MEAL_{slot_upper}"
    )

    messages.success(
        request,
        f"Test {slot_upper} message generated for {recipient_phone}! You can preview or send via WhatsApp Web."
    )
    return redirect('restaurant:meal_whatsapp_dashboard')


