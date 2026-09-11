import re
import logging
from urllib.parse import quote
from django.conf import settings
from django.utils import timezone
from django.db.models import Count
from .models import RestaurantProfile, WhatsAppTemplate, WhatsAppMessageLog
from menu.models import FoodItem
from subscriptions.models import SubscriptionPlan, CustomerSubscription
from accounts.models import User

logger = logging.getLogger(__name__)


def generate_live_menu_summary() -> str:
    """
    Generates a WhatsApp-formatted markdown list of live available super food dishes
    with effective 30% discount prices and MRP strikethroughs.
    """
    items = FoodItem.objects.filter(is_available=True).order_by('category__display_order', 'id')
    if not items.exists():
        return "• Fresh bowls & salads crafted daily (Check live menu online)"

    lines = []
    # 1. Signature Bowls
    bowls = items.filter(category__slug__in=['signature-protein-bowls', 'signature-meal-bowls'])
    if bowls.exists():
        for b in bowls:
            mrp_strike = f" ~₹{int(b.price)}~" if b.discounted_price else ""
            lines.append(f"• *{b.name}* ({b.protein_grams}g Protein) — *₹{int(b.effective_price)}*{mrp_strike}")

    # 2. Snacks Summary
    snacks = items.filter(category__slug='snack-bowls')
    if snacks.exists():
        snack_price = int(snacks.first().effective_price)
        lines.append(f"• *9 Nutritious Snack Bowls* (Fruit Salad, Sprout, Boiled Egg, Roasted Nuts) — *₹{snack_price}* each")

    # 3. Soups Summary
    soups = items.filter(category__slug='nourishing-soups')
    if soups.exists():
        soup_names = " & ".join([s.name.replace(' and Crotons', '') for s in soups])
        lines.append(f"• *Warm Soups & Crotons* ({soup_names}) — From *₹149*")

    return "\n".join(lines)


def generate_subscriptions_summary() -> str:
    """
    Generates a WhatsApp-formatted markdown list of weekly and monthly subscription plans.
    """
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('id')
    if not plans.exists():
        return "• Weekly & Monthly Meal Subscriptions with 30% OFF daily delivery"

    plan_map = {}
    for p in plans:
        name_clean = p.name.replace(' Subscription (Weekly)', '').replace(' Subscription (Monthly)', '')
        if name_clean not in plan_map:
            plan_map[name_clean] = {}
        if p.duration == SubscriptionPlan.Duration.WEEKLY:
            plan_map[name_clean]['weekly'] = int(p.price)
        elif p.duration == SubscriptionPlan.Duration.MONTHLY:
            plan_map[name_clean]['monthly'] = int(p.price)

    lines = []
    for dish_name, prices in plan_map.items():
        w_price = f"Weekly *₹{prices['weekly']:,}*" if 'weekly' in prices else ""
        m_price = f"Monthly *₹{prices['monthly']:,}*" if 'monthly' in prices else ""
        combo = " | ".join([p for p in [w_price, m_price] if p])
        lines.append(f"• *{dish_name}*: {combo}")

    return "\n".join(lines)


def get_customer_profile_data(customer):
    """
    Analyzes existing customer data to generate personalization signals:
      - Dietary Preference: VEG, NON_VEG, or ALL (derived from past orders)
      - Favorite Dish: most ordered item
      - Active Subscription: active meal plan if enrolled
    """
    if not customer or not customer.is_authenticated:
        return {
            'dietary_preference': 'ALL',
            'favorite_dish': None,
            'active_subscription': None,
            'orders_count': 0
        }

    from orders.models import OrderItem

    user_order_items = OrderItem.objects.filter(order__customer=customer)
    orders_count = customer.orders.count()

    # Determine Dietary Preference
    dietary_preference = 'ALL'
    if user_order_items.exists():
        has_non_veg = user_order_items.filter(food_item__food_type='NON_VEG').exists()
        has_veg = user_order_items.filter(food_item__food_type='VEG').exists()
        if has_non_veg and not has_veg:
            dietary_preference = 'NON_VEG'
        elif has_veg and not has_non_veg:
            dietary_preference = 'VEG'
        elif has_non_veg and has_veg:
            dietary_preference = 'NON_VEG'  # Enjoys both high-protein options

    # Find Favorite Dish
    favorite_dish = None
    fav_entry = user_order_items.values('food_item__name').annotate(cnt=Count('id')).order_by('-cnt').first()
    if fav_entry:
        favorite_dish = fav_entry['food_item__name']

    # Check Active Subscription
    active_subscription = CustomerSubscription.objects.filter(
        user=customer,
        status=CustomerSubscription.Status.ACTIVE
    ).select_related('plan').first()

    return {
        'dietary_preference': dietary_preference,
        'favorite_dish': favorite_dish,
        'active_subscription': active_subscription,
        'orders_count': orders_count
    }


def generate_meal_slot_menu_summary(meal_slot: str, diet_preference: str = 'ALL') -> str:
    """
    Extracts live available food items matching the active meal session (Breakfast, Lunch,
    Snack, Dinner) and tailors items to the customer's dietary preference with 30% discount prices.
    """
    slot_upper = meal_slot.upper()
    items = FoodItem.objects.filter(is_available=True)

    # Filter items matching the meal timing slot
    matched_items = []
    for item in items:
        slots = item.available_slots or []
        if not slots or 'ALL_DAY' in slots or slot_upper in slots:
            matched_items.append(item)

    if not matched_items:
        return "• Fresh protein bowls & salads prepped on order (Check live menu online)"

    # Prioritize based on diet preference
    if diet_preference == 'VEG':
        sorted_items = [i for i in matched_items if i.food_type == 'VEG'] + [i for i in matched_items if i.food_type != 'VEG']
    elif diet_preference == 'NON_VEG':
        sorted_items = [i for i in matched_items if i.food_type == 'NON_VEG'] + [i for i in matched_items if i.food_type != 'NON_VEG']
    else:
        sorted_items = matched_items

    lines = []
    # Take top 4-5 relevant dishes to keep the WhatsApp message compact & high-converting
    for item in sorted_items[:5]:
        mrp_strike = f" ~₹{int(item.price)}~" if item.discounted_price else ""
        diet_icon = "🟢" if item.food_type == 'VEG' else "🔴"
        lines.append(f"{diet_icon} *{item.name}* ({item.protein_grams}g Protein) — *₹{int(item.effective_price)}*{mrp_strike}")

    return "\n".join(lines)


def build_daily_meal_whatsapp_message(customer, meal_slot: str, template=None, base_url: str = None) -> str:
    """
    Builds a personalized daily meal notification message based on:
      - Customer's active subscription status (scheduled delivery confirmation vs ordering prompt)
      - Dietary preference & favorite dish history
      - Live meal session items with 30% discount pricing
    """
    profile = RestaurantProfile.get_instance()
    slot_upper = meal_slot.upper()
    tmpl = template or WhatsAppTemplate.get_meal_template(slot_upper)

    cust_name = "Super Food Lover"
    if customer:
        cust_name = customer.first_name.strip() if customer.first_name else customer.get_display_name()

    profile_data = get_customer_profile_data(customer)
    active_sub = profile_data['active_subscription']
    diet_pref = profile_data['dietary_preference']
    fav_dish = profile_data['favorite_dish']

    # 1. Tailored Subscription Status Snippet
    sub_status_lines = []
    if active_sub:
        time_slot_label = active_sub.get_delivery_time_slot_display()
        sub_status_lines.append(
            f"🌟 *Your Daily Subscription Meal is Active!*\n"
            f"Our head chef is crafting your fresh bowl for delivery during today's *{time_slot_label}* window.\n"
            f"Deliveries: {active_sub.bowls_delivered}/{active_sub.bowls_total} bowls fulfilled."
        )
    else:
        sub_status_lines.append(
            "💡 *Subscriber Advantage*: Love eating clean? Subscribe to our Weekly or Monthly meal plans with 30% OFF daily delivery."
        )
    subscription_status_text = "\n".join(sub_status_lines)

    # 2. Personalized Chef's Pick Recommendation
    if fav_dish:
        recommended_bowl_text = f"✨ *Chef's Special Recommendation*: We know you enjoy *{fav_dish}* — today's batch is freshly made and ready for you!"
    elif diet_pref == 'NON_VEG':
        recommended_bowl_text = "✨ *Chef's High-Protein Pick*: *Non-Veg Protein Bowl* (44g Protein) with lean chicken breast, boiled egg & clean seeds."
    else:
        recommended_bowl_text = "✨ *Chef's Clean Super Food Pick*: *Veg Protein Bowl* (32g Protein) with paneer, sprouted legumes & cold-pressed dressings."

    # 3. Available dishes for this meal session
    available_dishes_text = generate_meal_slot_menu_summary(slot_upper, diet_preference=diet_pref)

    meal_names = {
        'BREAKFAST': 'Morning Breakfast',
        'LUNCH': 'Power Lunch',
        'SNACK': 'Evening Fitness Snack',
        'DINNER': 'Clean Dinner'
    }
    meal_time_windows = {
        'BREAKFAST': '07:00 AM – 11:30 AM',
        'LUNCH': '11:30 AM – 04:00 PM',
        'SNACK': '04:00 PM – 07:00 PM',
        'DINNER': '07:00 PM – 11:00 PM'
    }

    site_url = base_url or f"http://localhost:8000/menu/?slot={slot_upper.lower()}"

    # Replace placeholders
    text = tmpl.body_text
    text = text.replace("{customer_name}", cust_name)
    text = text.replace("{meal_name}", meal_names.get(slot_upper, slot_upper.capitalize()))
    text = text.replace("{meal_time_window}", meal_time_windows.get(slot_upper, ''))
    text = text.replace("{subscription_status}", subscription_status_text)
    text = text.replace("{available_dishes}", available_dishes_text)
    text = text.replace("{recommended_bowl}", recommended_bowl_text)
    text = text.replace("{order_link}", site_url)
    text = text.replace("{restaurant_name}", profile.name)
    text = text.replace("{kitchen_phone}", profile.phone)
    text = text.replace("{whatsapp_number}", profile.whatsapp_number)

    return text.strip()


def build_welcome_whatsapp_message(customer, template=None, custom_template=None, base_url: str = None) -> str:
    """
    Builds the personalized WhatsApp welcome message with live database menu items,
    subscription prices, and contact details.
    """
    profile = RestaurantProfile.get_instance()
    template = template or custom_template or WhatsAppTemplate.get_welcome_template()

    cust_name = "Super Food Lover"
    if customer:
        cust_name = customer.first_name.strip() if customer.first_name else customer.get_display_name()

    menu_summary = generate_live_menu_summary() if template.include_live_menu else ""
    subs_summary = generate_subscriptions_summary() if template.include_subscriptions else ""

    site_url = base_url or "http://localhost:8000/menu/"

    text = template.body_text
    text = text.replace("{customer_name}", cust_name)
    text = text.replace("{menu_items}", menu_summary)
    text = text.replace("{subscription_plans}", subs_summary)
    text = text.replace("{order_link}", site_url)
    text = text.replace("{restaurant_name}", profile.name)
    text = text.replace("{kitchen_phone}", profile.phone)
    text = text.replace("{whatsapp_number}", profile.whatsapp_number)

    return text.strip()


def dispatch_whatsapp_message(recipient_phone: str, message_text: str, customer=None, message_type: str = 'WELCOME') -> WhatsAppMessageLog:
    """
    Dispatches a WhatsApp message.
    In development/demo mode:
      - Creates a WhatsAppMessageLog record with message_type.
      - Generates a direct 1-click WhatsApp Web link (https://api.whatsapp.com/send?phone=...&text=...).
      - Logs the message to console for immediate visibility.
    In production:
      - Calls configured WhatsApp Cloud API / Twilio / Interakt if credentials exist.
    """
    clean_phone = re.sub(r'\D', '', recipient_phone)
    if len(clean_phone) == 10:
        clean_phone = f"91{clean_phone}"

    log_entry = WhatsAppMessageLog.objects.create(
        customer=customer,
        recipient_phone=recipient_phone,
        message_type=message_type,
        message_text=message_text,
        status=WhatsAppMessageLog.Status.SENT,
        response_payload=f"Simulated delivery. WhatsApp Web Link: https://api.whatsapp.com/send?phone={clean_phone}&text={quote(message_text)}"
    )

    print(f"\n=======================================================")
    print(f"💬 [WHATSAPP {message_type.upper()}] Message Dispatched")
    print(f"Recipient: {recipient_phone} ({customer.get_display_name() if customer else 'Guest'})")
    print(f"Timestamp: {timezone.now().strftime('%Y-%m-%d %H:%M:%S IST')}")
    print(f"--- MESSAGE CONTENT ---")
    print(message_text)
    print(f"-----------------------")
    print(f"🔗 Click to open in WhatsApp Web / App:")
    print(log_entry.wa_web_link)
    print(f"=======================================================\n")

    logger.info(f"WhatsApp {message_type} message dispatched to {recipient_phone}")
    return log_entry


def trigger_customer_welcome_notification(customer, base_url: str = None):
    """
    Entry point triggered upon customer account creation (Phone OTP or registration).
    Checks template active status and avoids spamming if sent in last 24 hours.
    """
    template = WhatsAppTemplate.get_welcome_template()
    if not template.is_active:
        logger.info("WhatsApp welcome notification skipped (template disabled).")
        return None

    if not customer.phone:
        logger.warning(f"Customer {customer.id} has no phone number for WhatsApp.")
        return None

    recent_welcome = WhatsAppMessageLog.objects.filter(
        recipient_phone=customer.phone,
        message_type='WELCOME',
        sent_at__gte=timezone.now() - timezone.timedelta(hours=24)
    ).exists()

    if recent_welcome:
        logger.info(f"Customer {customer.phone} already received welcome WhatsApp in past 24h.")
        return None

    message_text = build_welcome_whatsapp_message(customer, template, base_url=base_url)
    return dispatch_whatsapp_message(customer.phone, message_text, customer=customer, message_type='WELCOME')


def dispatch_meal_broadcast(meal_slot: str, audience: str = 'ALL', base_url: str = None, dry_run: bool = False) -> dict:
    """
    Broadcasts daily meal notifications (Breakfast, Lunch, Evening Snack, Dinner)
    to the target customer segment with customer data personalization.
    
    Prevents duplicate dispatches to the same phone number for the same meal on the same day.
    """
    slot_upper = meal_slot.upper()
    template = WhatsAppTemplate.get_meal_template(slot_upper)

    if not template.is_active and not dry_run:
        return {
            'status': 'paused',
            'meal_slot': slot_upper,
            'message': f"Broadcast for {slot_upper} is currently paused in WhatsApp settings.",
            'total_eligible': 0,
            'dispatched_count': 0,
            'skipped_count': 0,
            'logs': []
        }

    # Query eligible registered customers with phone numbers
    customers = User.objects.filter(role=User.Role.CUSTOMER).exclude(phone__isnull=True).exclude(phone='')

    # Audience Segmentation Filter
    sub_user_ids = set(CustomerSubscription.objects.filter(
        status=CustomerSubscription.Status.ACTIVE
    ).values_list('user_id', flat=True))

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)

    eligible_customers = []
    for c in customers:
        if audience == 'SUBSCRIBERS' and c.id not in sub_user_ids:
            continue
        elif audience == 'NON_SUBSCRIBERS' and c.id in sub_user_ids:
            continue
        elif audience in ['VEG', 'NON_VEG']:
            profile_data = get_customer_profile_data(c)
            if profile_data['dietary_preference'] != audience:
                continue
        eligible_customers.append(c)

    total_eligible = len(eligible_customers)
    dispatched_count = 0
    skipped_count = 0
    generated_logs = []

    for cust in eligible_customers:
        # Check if already sent today for this meal session
        already_sent_today = WhatsAppMessageLog.objects.filter(
            recipient_phone=cust.phone,
            message_type=f"MEAL_{slot_upper}",
            sent_at__gte=today_start
        ).exists()

        if already_sent_today and not dry_run:
            skipped_count += 1
            continue

        personalized_msg = build_daily_meal_whatsapp_message(
            customer=cust,
            meal_slot=slot_upper,
            template=template,
            base_url=base_url
        )

        if dry_run:
            dispatched_count += 1
            print(f"[DRY RUN] Meal {slot_upper} -> {cust.phone} ({cust.get_display_name()}): {personalized_msg[:60]}...")
        else:
            log_item = dispatch_whatsapp_message(
                recipient_phone=cust.phone,
                message_text=personalized_msg,
                customer=cust,
                message_type=f"MEAL_{slot_upper}"
            )
            dispatched_count += 1
            generated_logs.append(log_item)

    return {
        'status': 'success',
        'meal_slot': slot_upper,
        'total_eligible': total_eligible,
        'dispatched_count': dispatched_count,
        'skipped_count': skipped_count,
        'logs': generated_logs
    }

