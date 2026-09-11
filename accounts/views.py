import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import User, Address
from .forms import CustomerRegistrationForm, LoginForm, UserProfileForm, AddressForm
from .decorators import customer_required
from .otp_service import generate_and_send_otp, verify_otp, get_or_create_customer_by_phone, normalize_phone
from restaurant.whatsapp_service import trigger_customer_welcome_notification


def transfer_guest_cart(request, user, session_key=None):
    """
    Transfers active items from an anonymous session cart to the logged-in user's cart.
    Accepts explicit session_key to handle session rotation during login().
    """
    try:
        from cart.models import Cart
        s_key = session_key or request.session.session_key
        if s_key:
            guest_cart = Cart.objects.filter(session_key=s_key).first()
            if guest_cart and guest_cart.items.exists():
                user_cart, _ = Cart.objects.get_or_create(user=user)
                for item in guest_cart.items.all():
                    existing_item = user_cart.items.filter(food_item=item.food_item).first()
                    if existing_item:
                        existing_item.quantity += item.quantity
                        existing_item.save()
                    else:
                        item.cart = user_cart
                        item.save()
                guest_cart.delete()
    except Exception:
        pass


def register_view(request):
    """
    Customer registration view for Nutrient – The Super Food.
    Also dispatches automated WhatsApp welcome catalog and transfers guest cart.
    """
    if request.user.is_authenticated:
        return redirect('menu:food_list')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            guest_session_key = request.session.session_key
            user = form.save()
            login(request, user)
            
            # Transfer any cart items added prior to registration
            transfer_guest_cart(request, user, session_key=guest_session_key)

            # Automatically dispatch welcome WhatsApp message with live 30% discount menu
            try:
                base_url = request.build_absolute_uri(reverse('menu:food_list'))
                trigger_customer_welcome_notification(user, base_url=base_url)
            except Exception:
                pass

            messages.success(
                request,
                f"Welcome to Nutrient – The Super Food, {user.first_name}! Start exploring clean, protein-rich meals."
            )
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('menu:food_list')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """
    User login view supporting dual authentication modes:
      1. Fast Phone Number OTP Login (for diners / mobile users)
      2. Traditional Password Login (for Admins, Delivery Fleet, & password accounts)
    """
    if request.user.is_authenticated:
        if request.user.is_restaurant_admin:
            return redirect('restaurant:dashboard')
        elif request.user.is_delivery_partner:
            return redirect('delivery:dashboard')
        return redirect('menu:food_list')

    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            guest_session_key = request.session.session_key
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_display_name()}!")

            # Transfer guest cart to user cart
            transfer_guest_cart(request, user, session_key=guest_session_key)

            if next_url:
                return redirect(next_url)

            # Role-based dashboard routing
            if user.is_restaurant_admin:
                return redirect('restaurant:dashboard')
            elif user.is_delivery_partner:
                return redirect('delivery:dashboard')
            return redirect('menu:food_list')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = LoginForm()

    dev_last_otp = request.session.get('dev_last_otp') if settings.DEBUG else None

    return render(request, 'accounts/login.html', {
        'form': form,
        'next': next_url,
        'dev_last_otp': dev_last_otp,
    })


@require_POST
def send_otp_view(request):
    """
    Generates and dispatches a 6-digit OTP to the customer's phone number.
    Enforces 60-second cooldown and 10-minute expiry.
    Supports both AJAX / JSON API and standard form POST.
    """
    is_json = request.content_type == 'application/json' or request.headers.get('x-requested-with') == 'XMLHttpRequest'
    
    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            phone = body.get('phone', '')
        except Exception:
            phone = ''
    else:
        phone = request.POST.get('phone', '')

    success, message, otp_code = generate_and_send_otp(phone, request=request)

    if is_json:
        return JsonResponse({
            'success': success,
            'message': message,
            'phone': phone,
            'dev_otp': otp_code if settings.DEBUG else None
        })

    if success:
        messages.success(request, message)
        return redirect(f"{reverse('accounts:login')}?step=otp&phone={phone}")
    else:
        messages.error(request, message)
        return redirect('accounts:login')


@require_POST
def verify_otp_view(request):
    """
    Validates user OTP code. On success:
      - Authenticates or creates customer account.
      - Automatically transfers guest cart items to the user.
      - Dispatches automated WhatsApp welcome message with live menu & subscriptions.
      - Redirects seamlessly to destination or menu.
    """
    is_json = request.content_type == 'application/json' or request.headers.get('x-requested-with') == 'XMLHttpRequest'
    
    if request.content_type == 'application/json':
        try:
            body = json.loads(request.body)
            phone = body.get('phone', '')
            code = body.get('otp_code', body.get('code', ''))
            first_name = body.get('first_name', '')
            next_url = body.get('next', '')
        except Exception:
            phone = ''
            code = ''
            first_name = ''
            next_url = ''
    else:
        phone = request.POST.get('phone', '')
        code = request.POST.get('otp_code', request.POST.get('code', ''))
        first_name = request.POST.get('first_name', '')
        next_url = request.POST.get('next', '')

    success, message, verified_phone = verify_otp(phone, code)

    if not success:
        if is_json:
            return JsonResponse({'success': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect(f"{reverse('accounts:login')}?step=otp&phone={phone}")

    # Phone verified! Retrieve or auto-create customer account
    user, created = get_or_create_customer_by_phone(verified_phone, first_name=first_name)
    guest_session_key = request.session.session_key
    login(request, user)

    # Transfer active guest cart to user
    transfer_guest_cart(request, user, session_key=guest_session_key)

    # Trigger WhatsApp welcome catalog notification for new users
    if created:
        try:
            base_url = request.build_absolute_uri(reverse('menu:food_list'))
            trigger_customer_welcome_notification(user, base_url=base_url)
        except Exception:
            pass

    # Determine destination redirect URL
    if next_url:
        target_url = next_url
    elif user.is_restaurant_admin:
        target_url = reverse('restaurant:dashboard')
    elif user.is_delivery_partner:
        target_url = reverse('delivery:dashboard')
    else:
        target_url = reverse('menu:food_list')

    welcome_greeting = f"Welcome to Nutrient, {user.get_display_name()}!" if created else f"Welcome back, {user.get_display_name()}!"
    messages.success(request, welcome_greeting)

    if is_json:
        return JsonResponse({
            'success': True,
            'message': welcome_greeting,
            'redirect_url': target_url,
            'is_new_user': created
        })

    return redirect(target_url)


def logout_view(request):
    """Logs out the active user."""
    logout(request)
    messages.info(request, "You have been logged out successfully. Stay healthy!")
    return redirect('menu:food_list')


@login_required
def profile_view(request):
    """
    Customer profile view to manage personal info, phone and avatar.
    """
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile details have been updated.")
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)

    default_address = request.user.addresses.filter(is_default=True).first()
    recent_orders = request.user.orders.all()[:5]

    context = {
        'form': form,
        'default_address': default_address,
        'recent_orders': recent_orders,
    }
    return render(request, 'accounts/profile.html', context)


# ==========================================
# Address Management Views
# ==========================================

@login_required
def address_list_view(request):
    """Lists all saved addresses for the customer."""
    addresses = request.user.addresses.all()
    return render(request, 'accounts/address_list.html', {'addresses': addresses})


@login_required
def address_create_view(request):
    """Creates a new delivery address."""
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            # If it's the user's first address, automatically make it default
            if not request.user.addresses.exists():
                address.is_default = True
            address.save()
            messages.success(request, "New delivery address saved.")
            if next_url:
                return redirect(next_url)
            return redirect('accounts:address_list')
    else:
        initial_data = {
            'contact_name': request.user.get_display_name(),
            'contact_phone': request.user.phone or '',
            'city': 'Hyderabad',
            'state': 'Telangana',
        }
        form = AddressForm(initial=initial_data)

    return render(request, 'accounts/address_form.html', {
        'form': form,
        'title': 'Add New Address',
        'next': next_url,
    })


@login_required
def address_update_view(request, pk):
    """Updates an existing delivery address."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Delivery address updated.")
            if next_url:
                return redirect(next_url)
            return redirect('accounts:address_list')
    else:
        form = AddressForm(instance=address)

    return render(request, 'accounts/address_form.html', {
        'form': form,
        'title': 'Edit Address',
        'address': address,
        'next': next_url,
    })


@login_required
def address_delete_view(request, pk):
    """Deletes an address."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        address.delete()
        messages.success(request, "Address removed.")
        return redirect('accounts:address_list')
    return render(request, 'accounts/address_confirm_delete.html', {'address': address})


@login_required
def address_set_default_view(request, pk):
    """Sets an address as default."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.is_default = True
    address.save()
    messages.success(request, f"'{address.get_address_type_display()}' address set as default delivery address.")
    next_url = request.GET.get('next') or ''
    if next_url:
        return redirect(next_url)
    return redirect('accounts:address_list')
