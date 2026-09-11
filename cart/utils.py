from decimal import Decimal
from restaurant.models import RestaurantProfile
from .models import Cart, CartItem
from menu.models import FoodItem


def get_or_create_cart(request):
    """
    Retrieves or initializes the active cart for an authenticated user or guest session.
    """
    if request.user.is_authenticated:
        cart, created = Cart.objects.get_or_create(user=request.user)
    else:
        if not request.session.session_key:
            request.session.create()
        session_key = request.session.session_key
        cart, created = Cart.objects.get_or_create(session_key=session_key, user=None)
    return cart


def get_cart_summary(cart):
    """
    Calculates detailed financial and nutritional breakdown for a cart:
      - Subtotal
      - GST Tax amount (e.g. 5%)
      - Delivery fee (free if subtotal >= threshold)
      - Grand total
      - Free delivery progress
      - Minimum order validation
      - Nutritional totals (Calories, Protein, Carbs, Fats)
    """
    profile = RestaurantProfile.get_instance()
    
    # Financial policies from restaurant profile
    tax_percentage = profile.tax_percentage or Decimal('5.00')
    default_delivery = profile.default_delivery_charge or Decimal('40.00')
    free_delivery_threshold = profile.free_delivery_threshold or Decimal('500.00')
    min_order_value = profile.min_order_value or Decimal('199.00')

    items = cart.items.select_related('food_item', 'food_item__category').all()
    
    subtotal = Decimal('0.00')
    total_calories = 0
    total_protein = Decimal('0.0')
    total_carbs = Decimal('0.0')
    total_fats = Decimal('0.0')
    total_items = 0

    for item in items:
        subtotal += item.subtotal
        total_items += item.quantity
        total_calories += item.total_calories
        total_protein += item.total_protein
        total_carbs += (item.food_item.carbs_grams * item.quantity)
        total_fats += (item.food_item.fats_grams * item.quantity)

    # Tax Calculation
    if subtotal > 0:
        tax_amount = ((subtotal * tax_percentage) / Decimal('100.00')).quantize(Decimal('0.01'))
    else:
        tax_amount = Decimal('0.00')

    # Delivery Charge Calculation
    if subtotal == 0:
        delivery_fee = Decimal('0.00')
        free_delivery_remaining = free_delivery_threshold
        free_delivery_progress = 0
    elif subtotal >= free_delivery_threshold:
        delivery_fee = Decimal('0.00')
        free_delivery_remaining = Decimal('0.00')
        free_delivery_progress = 100
    else:
        delivery_fee = default_delivery
        free_delivery_remaining = (free_delivery_threshold - subtotal).quantize(Decimal('0.01'))
        free_delivery_progress = min(100, int((subtotal / free_delivery_threshold) * 100))

    discount_amount = Decimal('0.00')
    total_amount = (subtotal + tax_amount + delivery_fee - discount_amount).quantize(Decimal('0.01'))

    is_min_order_met = subtotal >= min_order_value
    min_order_shortfall = max(Decimal('0.00'), min_order_value - subtotal).quantize(Decimal('0.01'))

    return {
        'cart': cart,
        'items': items,
        'total_items': total_items,
        'subtotal': subtotal,
        'tax_percentage': tax_percentage,
        'tax_amount': tax_amount,
        'delivery_fee': delivery_fee,
        'is_free_delivery': delivery_fee == Decimal('0.00') and subtotal > 0,
        'free_delivery_threshold': free_delivery_threshold,
        'free_delivery_remaining': free_delivery_remaining,
        'free_delivery_progress': free_delivery_progress,
        'discount_amount': discount_amount,
        'total_amount': total_amount,
        'min_order_value': min_order_value,
        'is_min_order_met': is_min_order_met,
        'min_order_shortfall': min_order_shortfall,
        # Nutrition aggregations
        'total_calories': total_calories,
        'total_protein': total_protein.quantize(Decimal('0.1')),
        'total_carbs': total_carbs.quantize(Decimal('0.1')),
        'total_fats': total_fats.quantize(Decimal('0.1')),
    }
