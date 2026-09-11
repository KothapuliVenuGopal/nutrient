import json
import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from accounts.models import Address
from menu.models import FoodItem, CustomizationGroup
from .models import SubscriptionPlan, CustomerSubscription, DailySubscriptionDelivery


def subscription_plans_view(request):
    """
    Public catalog of weekly and monthly super food meal bowl subscription plans.
    """
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('display_order', 'id')
    weekly_plans = plans.filter(duration=SubscriptionPlan.Duration.WEEKLY)
    monthly_plans = plans.filter(duration=SubscriptionPlan.Duration.MONTHLY)

    context = {
        'plans': plans,
        'weekly_plans': weekly_plans,
        'monthly_plans': monthly_plans,
    }
    return render(request, 'subscriptions/plans.html', context)


@login_required
def subscribe_view(request, plan_id):
    """
    Subscribe checkout: address selection, time slot, start date, and default bowl customization.
    """
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
    addresses = Address.objects.filter(user=request.user).order_by('-is_default', '-created_at')

    # Find the corresponding FoodItem to load customization groups
    food_slug_map = {
        SubscriptionPlan.BowlType.VEG_PROTEIN: 'veg-protein-bowl',
        SubscriptionPlan.BowlType.NON_VEG_PROTEIN: 'non-veg-protein-bowl',
        SubscriptionPlan.BowlType.VEG_MEAL: 'veg-meal-bowl',
        SubscriptionPlan.BowlType.NON_VEG_MEAL: 'non-veg-meal-bowl',
    }
    target_slug = food_slug_map.get(plan.bowl_type)
    food_item = FoodItem.objects.filter(slug=target_slug).first()
    customization_groups = food_item.customization_groups.prefetch_related('options').all() if food_item else []

    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        time_slot = request.POST.get('time_slot', CustomerSubscription.TimeSlot.LUNCH)
        start_date_str = request.POST.get('start_date')
        special_instructions = request.POST.get('special_instructions', '').strip()
        customizations_json = request.POST.get('customizations_json', '{}')

        try:
            default_customization = json.loads(customizations_json) if customizations_json else {}
        except Exception:
            default_customization = {}

        if not default_customization or not default_customization.get('selected_options'):
            selected_options = {}
            for key, val in request.POST.lists():
                if key.startswith('custom_'):
                    group_name = key[7:]
                    selected_options[group_name] = val
            if selected_options:
                default_customization = {'selected_options': selected_options, 'extra_price': 0.00}

        if not address_id:
            messages.error(request, "Please select or add a delivery address for your subscription.")
            return redirect('subscriptions:subscribe', plan_id=plan.id)

        address = get_object_or_404(Address, id=address_id, user=request.user)

        today = timezone.localdate()
        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
                if start_date < today:
                    start_date = today
            except ValueError:
                start_date = today + datetime.timedelta(days=1)
        else:
            start_date = today + datetime.timedelta(days=1)

        # Calculate end date based on total bowls
        end_date = start_date + datetime.timedelta(days=plan.total_bowls - 1)

        # Create Subscription record
        subscription = CustomerSubscription.objects.create(
            user=request.user,
            plan=plan,
            status=CustomerSubscription.Status.ACTIVE,
            start_date=start_date,
            end_date=end_date,
            delivery_time_slot=time_slot,
            delivery_address=address,
            bowls_total=plan.total_bowls,
            bowls_delivered=0,
            default_customization=default_customization,
            special_instructions=special_instructions,
            payment_status='PAID',
            payment_method='ONLINE_MOCK'
        )

        # Automatically schedule daily deliveries
        for day_offset in range(plan.total_bowls):
            delivery_date = start_date + datetime.timedelta(days=day_offset)
            DailySubscriptionDelivery.objects.create(
                subscription=subscription,
                delivery_date=delivery_date,
                time_slot=time_slot,
                status=DailySubscriptionDelivery.Status.SCHEDULED,
                customization=default_customization
            )

        messages.success(
            request,
            f"🎉 Congratulations! You have successfully subscribed to the {plan.name}. "
            f"Your daily super food deliveries start on {start_date.strftime('%d %b, %Y')}."
        )
        return redirect('subscriptions:my_subscriptions')

    default_start_date = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()

    context = {
        'plan': plan,
        'addresses': addresses,
        'food_item': food_item,
        'customization_groups': customization_groups,
        'default_start_date': default_start_date,
    }
    return render(request, 'subscriptions/subscribe.html', context)


@login_required
def my_subscriptions_view(request):
    """
    Customer subscription management dashboard with progress tracking and calendar.
    """
    subscriptions = CustomerSubscription.objects.filter(user=request.user).order_by('-created_at')
    active_subscription = subscriptions.filter(status__in=[CustomerSubscription.Status.ACTIVE, CustomerSubscription.Status.PAUSED]).first()

    upcoming_deliveries = []
    if active_subscription:
        today = timezone.localdate()
        upcoming_deliveries = active_subscription.daily_deliveries.filter(
            delivery_date__gte=today
        ).order_by('delivery_date')[:14]

    # Find the corresponding FoodItem to allow customizing upcoming meals
    food_item = None
    customization_groups = []
    if active_subscription:
        food_slug_map = {
            SubscriptionPlan.BowlType.VEG_PROTEIN: 'veg-protein-bowl',
            SubscriptionPlan.BowlType.NON_VEG_PROTEIN: 'non-veg-protein-bowl',
            SubscriptionPlan.BowlType.VEG_MEAL: 'veg-meal-bowl',
            SubscriptionPlan.BowlType.NON_VEG_MEAL: 'non-veg-meal-bowl',
        }
        target_slug = food_slug_map.get(active_subscription.plan.bowl_type)
        food_item = FoodItem.objects.filter(slug=target_slug).first()
        if food_item:
            customization_groups = food_item.customization_groups.prefetch_related('options').all()

    context = {
        'subscriptions': subscriptions,
        'active_subscription': active_subscription,
        'upcoming_deliveries': upcoming_deliveries,
        'food_item': food_item,
        'customization_groups': customization_groups,
    }
    return render(request, 'subscriptions/my_subscriptions.html', context)


@login_required
@require_POST
def customize_daily_meal_ajax(request, delivery_id):
    """
    Allows subscriber to customize ingredients for a specific future scheduled delivery.
    """
    delivery = get_object_or_404(DailySubscriptionDelivery, id=delivery_id)

    # Security: Verify ownership
    if delivery.subscription.user != request.user:
        return JsonResponse({'success': False, 'message': 'Unauthorized'}, status=403)

    if not delivery.can_customize:
        return JsonResponse({'success': False, 'message': 'This meal can no longer be edited.'}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
        customization = data.get('customization') or data.get('customizations', {})
        delivery_notes = data.get('delivery_notes') or data.get('notes', '')
    except Exception:
        customization = {}
        delivery_notes = ''

    delivery.customization = customization
    if delivery_notes:
        delivery.delivery_notes = delivery_notes
    delivery.save()

    return JsonResponse({
        'success': True,
        'message': f"Updated meal customization for {delivery.delivery_date.strftime('%d %b, %Y')}!",
        'delivery_id': delivery.id
    })


@login_required
@require_POST
def toggle_pause_subscription_ajax(request, subscription_id):
    """
    Allows subscriber to pause or resume an active subscription.
    """
    subscription = get_object_or_404(CustomerSubscription, id=subscription_id, user=request.user)

    if subscription.status not in [CustomerSubscription.Status.ACTIVE, CustomerSubscription.Status.PAUSED]:
        return JsonResponse({'success': False, 'message': 'This subscription cannot be modified.'}, status=400)

    subscription.toggle_pause()

    state_text = "paused" if subscription.is_paused else "resumed and active"
    return JsonResponse({
        'success': True,
        'message': f"Your subscription is now {state_text}.",
        'is_paused': subscription.is_paused,
        'status': subscription.status,
        'status_display': subscription.get_status_display()
    })
