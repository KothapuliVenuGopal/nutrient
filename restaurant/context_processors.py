from .models import RestaurantProfile


def restaurant_info(request):
    """
    Exposes single-restaurant brand metadata and operational status across all templates.
    """
    try:
        profile = RestaurantProfile.get_instance()
        is_open = profile.is_currently_open()
    except Exception:
        profile = None
        is_open = False

    return {
        'restaurant': profile,
        'is_kitchen_open': is_open,
    }
