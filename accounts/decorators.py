from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from .models import User


def role_required(*allowed_roles):
    """
    Decorator to restrict view access to users with specified roles.
    Redirects unauthenticated users to login, and unauthorized users with a warning message.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, "Please log in to access this page.")
                return redirect(f"{reverse('accounts:login')}?next={request.path}")
            
            # Superusers always have admin privilege
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if request.user.role not in allowed_roles:
                messages.error(request, "You do not have permission to access this area.")
                if request.user.role == User.Role.DELIVERY_PARTNER:
                    return redirect('delivery:dashboard')
                elif request.user.role == User.Role.RESTAURANT_ADMIN:
                    return redirect('restaurant:dashboard')
                return redirect('menu:food_list')

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def customer_required(view_func):
    """Restricts access to authenticated customers."""
    return role_required(User.Role.CUSTOMER)(view_func)


def restaurant_admin_required(view_func):
    """Restricts access to Restaurant Administrators & Kitchen Managers."""
    return role_required(User.Role.RESTAURANT_ADMIN)(view_func)


def delivery_partner_required(view_func):
    """Restricts access to Delivery Partners."""
    return role_required(User.Role.DELIVERY_PARTNER)(view_func)
