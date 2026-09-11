from .utils import get_or_create_cart


def cart_status(request):
    """
    Exposes active cart count and subtotal to all templates.
    """
    try:
        cart = get_or_create_cart(request)
        total_items = cart.total_items
        subtotal = cart.subtotal
    except Exception:
        total_items = 0
        subtotal = 0

    return {
        'cart_total_items': total_items,
        'cart_subtotal': subtotal,
    }
