import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from menu.models import FoodItem
from restaurant.models import RestaurantProfile
from .models import Cart, CartItem
from .utils import get_or_create_cart, get_cart_summary


def cart_detail_view(request):
    """
    Renders customer cart page with live financial and nutritional summary.
    """
    cart = get_or_create_cart(request)
    summary = get_cart_summary(cart)
    return render(request, 'cart/cart_detail.html', {'summary': summary})


@require_POST
def cart_add_view(request):
    """
    Adds a food item to customer's active cart.
    Accepts both JSON Fetch API and traditional form POST.
    """
    # Support JSON body or standard form POST
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = {}
    else:
        data = request.POST

    item_id = data.get('item_id')
    try:
        quantity = int(data.get('quantity', 1))
        if quantity < 1:
            quantity = 1
    except (ValueError, TypeError):
        quantity = 1

    special_instructions = data.get('special_instructions', '').strip()
    customizations = data.get('customizations') or {}
    if isinstance(customizations, str):
        try:
            customizations = json.loads(customizations)
        except Exception:
            customizations = {}

    import hashlib
    customization_hash = ''
    if customizations:
        hash_input = json.dumps(customizations, sort_keys=True)
        customization_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:16]

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json'

    # Check kitchen operational status
    profile = RestaurantProfile.get_instance()
    if not profile.is_accepting_orders:
        err_msg = "We are temporarily not accepting orders due to kitchen capacity. Please check back shortly."
        if is_ajax:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)
        messages.warning(request, err_msg)
        return redirect('menu:food_list')

    # Validate food item
    try:
        food_item = FoodItem.objects.get(id=item_id)
    except FoodItem.DoesNotExist:
        err_msg = "Selected super food item was not found."
        if is_ajax:
            return JsonResponse({'success': False, 'message': err_msg}, status=404)
        messages.error(request, err_msg)
        return redirect('menu:food_list')

    # 1. Chef Manual Stock Check
    if not food_item.is_available:
        err_msg = f"'{food_item.name}' is currently Sold Out. The Head Chef will restock it soon!"
        if is_ajax:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)
        messages.warning(request, err_msg)
        return redirect('menu:food_list')

    # 2. Meal Timing Slot Check
    if food_item.auto_timing_enabled and not food_item.is_slot_active():
        err_msg = f"'{food_item.name}' is not active during this hour. Meal timings: {food_item.timing_badge_text}."
        if is_ajax:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)
        messages.warning(request, err_msg)
        return redirect('menu:food_list')

    cart = get_or_create_cart(request)
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        food_item=food_item,
        customization_hash=customization_hash,
        defaults={
            'quantity': quantity,
            'special_instructions': special_instructions,
            'customizations': customizations,
        }
    )

    if not created:
        cart_item.quantity += quantity
        if special_instructions:
            cart_item.special_instructions = special_instructions
        if customizations:
            cart_item.customizations = customizations
        cart_item.save()

    summary = get_cart_summary(cart)

    success_msg = f"Added {quantity}x '{food_item.name}' to your cart."
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': success_msg,
            'cart_item_id': cart_item.id,
            'item_id': food_item.id,
            'item_name': food_item.name,
            'item_quantity': cart_item.quantity,
            'item_subtotal': str(cart_item.subtotal),
            'cart_total_items': summary['total_items'],
            'cart_subtotal': str(summary['subtotal']),
            'tax_amount': str(summary['tax_amount']),
            'delivery_fee': str(summary['delivery_fee']),
            'is_free_delivery': summary['is_free_delivery'],
            'free_delivery_remaining': str(summary['free_delivery_remaining']),
            'free_delivery_progress': summary['free_delivery_progress'],
            'total_amount': str(summary['total_amount']),
            'total_calories': summary['total_calories'],
            'total_protein': str(summary['total_protein']),
        })

    messages.success(request, success_msg)
    return redirect('cart:cart_detail')


@require_POST
def cart_update_quantity_view(request):
    """
    Updates item quantity (increase, decrease, set).
    If quantity reaches 0, the item is removed.
    """
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
        except Exception:
            data = {}
    else:
        data = request.POST

    cart_item_id = data.get('cart_item_id')
    item_id = data.get('item_id')
    customization_hash = data.get('customization_hash', '')
    action = data.get('action', 'set')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json'

    cart = get_or_create_cart(request)
    cart_item = None
    if cart_item_id:
        cart_item = CartItem.objects.filter(cart=cart, id=cart_item_id).first()
    if not cart_item and item_id:
        cart_item = CartItem.objects.filter(cart=cart, food_item_id=item_id, customization_hash=customization_hash).first()
    if not cart_item and item_id:
        cart_item = CartItem.objects.filter(cart=cart, food_item_id=item_id).first()

    if not cart_item:
        if is_ajax:
            return JsonResponse({'success': False, 'message': 'Item not found in cart'}, status=404)
        return redirect('cart:cart_detail')

    item_removed = False
    if action == 'increase':
        cart_item.quantity += 1
        cart_item.save()
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
            item_removed = True
    elif action == 'set':
        try:
            new_qty = int(data.get('quantity', 1))
            if new_qty <= 0:
                cart_item.delete()
                item_removed = True
            else:
                cart_item.quantity = new_qty
                cart_item.save()
        except (ValueError, TypeError):
            pass

    summary = get_cart_summary(cart)

    if is_ajax:
        return JsonResponse({
            'success': True,
            'item_id': int(item_id),
            'item_removed': item_removed,
            'item_quantity': 0 if item_removed else cart_item.quantity,
            'item_subtotal': '0.00' if item_removed else str(cart_item.subtotal),
            'cart_total_items': summary['total_items'],
            'cart_subtotal': str(summary['subtotal']),
            'tax_amount': str(summary['tax_amount']),
            'delivery_fee': str(summary['delivery_fee']),
            'is_free_delivery': summary['is_free_delivery'],
            'free_delivery_remaining': str(summary['free_delivery_remaining']),
            'free_delivery_progress': summary['free_delivery_progress'],
            'total_amount': str(summary['total_amount']),
            'total_calories': summary['total_calories'],
            'total_protein': str(summary['total_protein']),
            'is_min_order_met': summary['is_min_order_met'],
            'min_order_shortfall': str(summary['min_order_shortfall']),
        })

    return redirect('cart:cart_detail')


@require_POST
def cart_remove_view(request, item_id):
    """
    Removes a single item completely from cart.
    Supports either cart_item_id or food_item_id.
    """
    cart = get_or_create_cart(request)
    cart_item_id = request.POST.get('cart_item_id') or request.GET.get('cart_item_id')
    if cart_item_id:
        CartItem.objects.filter(cart=cart, id=cart_item_id).delete()
    else:
        CartItem.objects.filter(cart=cart, food_item_id=item_id).delete()
    
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        summary = get_cart_summary(cart)
        return JsonResponse({
            'success': True,
            'item_id': item_id,
            'cart_total_items': summary['total_items'],
            'cart_subtotal': str(summary['subtotal']),
            'tax_amount': str(summary['tax_amount']),
            'delivery_fee': str(summary['delivery_fee']),
            'total_amount': str(summary['total_amount']),
            'total_calories': summary['total_calories'],
            'total_protein': str(summary['total_protein']),
        })

    messages.info(request, "Item removed from cart.")
    return redirect('cart:cart_detail')


@require_POST
def cart_clear_view(request):
    """
    Empties all items from the cart.
    """
    cart = get_or_create_cart(request)
    cart.clear()
    messages.info(request, "Your cart is now empty.")
    return redirect('cart:cart_detail')


def cart_api_summary(request):
    """
    Lightweight JSON endpoint for navbar badge & client synchronizations.
    """
    cart = get_or_create_cart(request)
    summary = get_cart_summary(cart)
    return JsonResponse({
        'total_items': summary['total_items'],
        'subtotal': str(summary['subtotal']),
        'total_amount': str(summary['total_amount']),
        'total_calories': summary['total_calories'],
        'total_protein': str(summary['total_protein']),
    })
