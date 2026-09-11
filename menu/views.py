from decimal import Decimal, DecimalException
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q, Avg
from accounts.decorators import restaurant_admin_required
from reviews.models import Review
from .models import Category, FoodItem
from .forms import CategoryForm, FoodItemForm


# ==========================================
# Meal Timing & Slot Helpers
# ==========================================

def get_current_meal_slot():
    """
    Returns current active meal slot and details based on IST time.
    Breakfast: 07:00 AM – 11:30 AM (420 to 690 mins)
    Lunch: 11:30 AM – 04:00 PM (690 to 960 mins)
    Snack: 04:00 PM – 07:00 PM (960 to 1140 mins)
    Dinner: 07:00 PM – 11:00 PM (1140 to 1380 mins)
    Closed: 11:00 PM – 07:00 AM (< 420 or >= 1380 mins)
    """
    from django.utils import timezone
    now = timezone.localtime()
    minutes = now.hour * 60 + now.minute

    if 420 <= minutes < 690:
        return {
            'code': 'BREAKFAST',
            'name': 'Breakfast',
            'timing': '07:00 AM – 11:30 AM',
            'is_open': True,
            'next_slot': 'Lunch (11:30 AM)'
        }
    elif 690 <= minutes < 960:
        return {
            'code': 'LUNCH',
            'name': 'Lunch',
            'timing': '11:30 AM – 04:00 PM',
            'is_open': True,
            'next_slot': 'Snack (04:00 PM)'
        }
    elif 960 <= minutes < 1140:
        return {
            'code': 'SNACK',
            'name': 'Snack',
            'timing': '04:00 PM – 07:00 PM',
            'is_open': True,
            'next_slot': 'Dinner (07:00 PM)'
        }
    elif 1140 <= minutes < 1380:
        return {
            'code': 'DINNER',
            'name': 'Dinner',
            'timing': '07:00 PM – 11:00 PM',
            'is_open': True,
            'next_slot': 'Breakfast Tomorrow (07:00 AM)'
        }
    else:
        return {
            'code': 'CLOSED',
            'name': 'Kitchen Closed',
            'timing': '11:00 PM – 07:00 AM',
            'is_open': False,
            'next_slot': 'Breakfast (07:00 AM)'
        }


# ==========================================
# Customer-Facing Menu Views
# ==========================================

def food_list(request):
    """
    Public customer-facing menu for Nutrient – The Super Food.
    Supports dynamic category filtering, meal slot filtering (Active Now, Breakfast, Lunch, Snack, Dinner, All),
    multi-facet dietary filters (Veg/Non-Veg/Vegan, High-Protein, Calorie-conscious),
    sorting (Protein, Calories, Price, Bestseller), and keyword search.
    """
    categories = Category.objects.filter(is_active=True).order_by('display_order', 'name')
    items_qs = FoodItem.objects.filter(is_available=True).select_related('category')

    current_slot = get_current_meal_slot()

    # Query Parameters
    selected_category_slug = request.GET.get('category', '').strip()
    selected_slot = request.GET.get('slot', 'active').strip().lower()
    selected_diet_type = request.GET.get('type', '').strip()
    selected_tag = request.GET.get('tag', '').strip()
    sort_by = request.GET.get('sort', 'recommended').strip()
    search_query = request.GET.get('q', '').strip()

    # 1. Category Filter
    active_category = None
    if selected_category_slug and selected_category_slug != 'all':
        active_category = categories.filter(slug=selected_category_slug).first()
        if active_category:
            items_qs = items_qs.filter(category=active_category)

    # 2. Dietary Type Filter (Veg, Non-Veg, Vegan)
    if selected_diet_type in [FoodItem.FoodType.VEG, FoodItem.FoodType.NON_VEG, FoodItem.FoodType.VEGAN]:
        items_qs = items_qs.filter(food_type=selected_diet_type)

    # 3. Health & Nutrition Badges Filter
    if selected_tag == 'high_protein':
        items_qs = items_qs.filter(is_high_protein=True)
    elif selected_tag == 'calorie_conscious':
        items_qs = items_qs.filter(is_calorie_conscious=True)
    elif selected_tag == 'gluten_free':
        items_qs = items_qs.filter(is_gluten_free=True)
    elif selected_tag == 'keto':
        items_qs = items_qs.filter(is_keto_friendly=True)
    elif selected_tag == 'bestseller':
        items_qs = items_qs.filter(is_bestseller=True)
    elif selected_tag == 'chef_special':
        items_qs = items_qs.filter(is_chef_special=True)

    # 4. Search Query
    if search_query:
        items_qs = items_qs.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )

    # 5. Sorting Engine
    if sort_by == 'protein_desc':
        items_qs = items_qs.order_by('-protein_grams', 'name')
    elif sort_by == 'calories_asc':
        items_qs = items_qs.order_by('calories', 'name')
    elif sort_by == 'price_asc':
        items_qs = items_qs.order_by('price', 'name')
    elif sort_by == 'price_desc':
        items_qs = items_qs.order_by('-price', 'name')
    else:  # Recommended / Popular
        items_qs = items_qs.order_by('-is_bestseller', '-is_chef_special', 'category__display_order', 'name')

    # 6. Meal Slot Filtering
    raw_items = list(items_qs)
    filtered_items = []
    for itm in raw_items:
        slots = itm.available_slots or []
        if selected_slot == 'active':
            if not current_slot['is_open'] or itm.is_slot_active():
                filtered_items.append(itm)
        elif selected_slot == 'breakfast':
            if 'BREAKFAST' in slots or 'ALL_DAY' in slots or not slots:
                filtered_items.append(itm)
        elif selected_slot == 'lunch':
            if 'LUNCH' in slots or 'ALL_DAY' in slots or not slots:
                filtered_items.append(itm)
        elif selected_slot == 'snack':
            if 'SNACK' in slots or 'ALL_DAY' in slots or not slots:
                filtered_items.append(itm)
        elif selected_slot == 'dinner':
            if 'DINNER' in slots or 'ALL_DAY' in slots or not slots:
                filtered_items.append(itm)
        else:  # 'all'
            filtered_items.append(itm)

    items = filtered_items

    # AJAX Response support for dynamic filtering
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('format') == 'json':
        items_data = []
        for itm in items:
            items_data.append({
                'id': itm.id,
                'name': itm.name,
                'slug': itm.slug,
                'category': itm.category.name,
                'food_type': itm.food_type,
                'price': str(itm.price),
                'discounted_price': str(itm.discounted_price) if itm.discounted_price else None,
                'effective_price': str(itm.effective_price),
                'discount_percentage': itm.discount_percentage,
                'calories': itm.calories,
                'protein_grams': str(itm.protein_grams),
                'carbs_grams': str(itm.carbs_grams),
                'fats_grams': str(itm.fats_grams),
                'is_high_protein': itm.is_high_protein,
                'is_calorie_conscious': itm.is_calorie_conscious,
                'is_bestseller': itm.is_bestseller,
                'is_available': itm.is_available,
                'is_orderable': itm.is_orderable,
                'status_badge': itm.current_status_badge,
                'timing_badge_text': itm.timing_badge_text,
                'image_url': itm.image.url if itm.image else None,
            })
        return JsonResponse({
            'success': True,
            'count': len(items_data),
            'items': items_data,
            'current_slot': current_slot
        })

    # Counts for Filter Badges
    total_active_items = FoodItem.objects.filter(is_available=True).count()
    high_protein_count = FoodItem.objects.filter(is_available=True, is_high_protein=True).count()
    calorie_conscious_count = FoodItem.objects.filter(is_available=True, is_calorie_conscious=True).count()
    bestseller_count = FoodItem.objects.filter(is_available=True, is_bestseller=True).count()

    testimonials = Review.objects.filter(
        is_approved=True,
        rating__gte=4
    ).select_related('customer', 'food_item').order_by('-created_at')[:4]

    context = {
        'categories': categories,
        'items': items,
        'active_category': active_category,
        'selected_category_slug': selected_category_slug,
        'selected_slot': selected_slot,
        'current_slot': current_slot,
        'selected_diet_type': selected_diet_type,
        'selected_tag': selected_tag,
        'sort_by': sort_by,
        'search_query': search_query,
        'total_active_items': total_active_items,
        'high_protein_count': high_protein_count,
        'calorie_conscious_count': calorie_conscious_count,
        'bestseller_count': bestseller_count,
        'testimonials': testimonials,
    }
    return render(request, 'menu/food_list.html', context)


def food_detail(request, slug):
    """
    Rich detail page for a specific super food dish.
    Displays detailed macro breakdown, visual macro ratio bars, ingredient details, customer reviews and related dishes.
    """
    item = get_object_or_404(FoodItem, slug=slug)
    
    # Calculate Macro Ratios for Visual Bar
    total_macros = item.protein_grams + item.carbs_grams + item.fats_grams
    if total_macros > 0:
        protein_ratio = int(round((item.protein_grams / total_macros) * 100))
        carbs_ratio = int(round((item.carbs_grams / total_macros) * 100))
        fats_ratio = 100 - (protein_ratio + carbs_ratio)
    else:
        protein_ratio, carbs_ratio, fats_ratio = 33, 33, 34

    # Related Super Foods in same category
    related_items = FoodItem.objects.filter(
        category=item.category,
        is_available=True
    ).exclude(pk=item.pk)[:3]

    # Customer Reviews & Average Rating
    reviews = item.reviews.filter(is_approved=True).select_related('customer')[:5]
    avg_rating = item.reviews.filter(is_approved=True).aggregate(Avg('rating'))['rating__avg']
    if avg_rating:
        avg_rating = round(avg_rating, 1)

    context = {
        'item': item,
        'total_macros': total_macros,
        'protein_ratio': protein_ratio,
        'carbs_ratio': carbs_ratio,
        'fats_ratio': fats_ratio,
        'related_items': related_items,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'reviews_count': item.reviews.filter(is_approved=True).count(),
    }
    return render(request, 'menu/food_detail.html', context)


# ==========================================
# Restaurant Admin: Category Management
# ==========================================

@restaurant_admin_required
def admin_category_list(request):
    """Lists categories with item counts and display ordering."""
    categories = Category.objects.annotate(items_count=Count('food_items')).order_by('display_order', 'name')
    return render(request, 'menu/admin_category_list.html', {'categories': categories})


@restaurant_admin_required
def admin_category_create(request):
    """Creates a new menu category."""
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' created successfully.")
            return redirect('menu:admin_category_list')
    else:
        form = CategoryForm()
    return render(request, 'menu/admin_category_form.html', {'form': form, 'title': 'Add New Category'})


@restaurant_admin_required
def admin_category_update(request, pk):
    """Edits an existing category."""
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' updated.")
            return redirect('menu:admin_category_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'menu/admin_category_form.html', {'form': form, 'title': f'Edit Category: {category.name}'})


@restaurant_admin_required
def admin_category_delete(request, pk):
    """Deletes a category."""
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f"Category '{name}' deleted.")
        return redirect('menu:admin_category_list')
    return render(request, 'menu/admin_confirm_delete.html', {
        'object_name': f"Category '{category.name}' and all its {category.food_items.count()} associated items",
        'cancel_url': 'menu:admin_category_list'
    })


# ==========================================
# Restaurant Admin: Food Item Management
# ==========================================

@restaurant_admin_required
def admin_food_list(request):
    """
    Management table for all food items.
    Supports filtering by category, food type, stock availability, and search.
    """
    items = FoodItem.objects.select_related('category').all()
    categories = Category.objects.all()

    category_id = request.GET.get('category')
    food_type = request.GET.get('type')
    availability = request.GET.get('available')
    search_query = request.GET.get('q', '').strip()

    if category_id:
        items = items.filter(category_id=category_id)
    if food_type:
        items = items.filter(food_type=food_type)
    if availability == '1':
        items = items.filter(is_available=True)
    elif availability == '0':
        items = items.filter(is_available=False)
    if search_query:
        items = items.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

    context = {
        'items': items,
        'categories': categories,
        'selected_category': category_id,
        'selected_type': food_type,
        'selected_availability': availability,
        'search_query': search_query,
    }
    return render(request, 'menu/admin_food_list.html', context)


@restaurant_admin_required
def admin_food_create(request):
    """Creates a new food item with nutrition facts."""
    if request.method == 'POST':
        form = FoodItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"Food item '{item.name}' added to menu.")
            return redirect('menu:admin_food_list')
    else:
        form = FoodItemForm(initial={'is_zero_preservative': True, 'is_available': True})
    return render(request, 'menu/admin_food_form.html', {'form': form, 'title': 'Add New Super Food Item'})


@restaurant_admin_required
def admin_food_update(request, pk):
    """Edits an existing food item."""
    item = get_object_or_404(FoodItem, pk=pk)
    if request.method == 'POST':
        form = FoodItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            updated_item = form.save()
            messages.success(request, f"Food item '{updated_item.name}' updated.")
            return redirect('menu:admin_food_list')
    else:
        form = FoodItemForm(instance=item)
    return render(request, 'menu/admin_food_form.html', {'form': form, 'title': f'Edit Item: {item.name}'})


@restaurant_admin_required
def admin_food_delete(request, pk):
    """Deletes a food item."""
    item = get_object_or_404(FoodItem, pk=pk)
    if request.method == 'POST':
        name = item.name
        item.delete()
        messages.success(request, f"Food item '{name}' deleted.")
        return redirect('menu:admin_food_list')
    return render(request, 'menu/admin_confirm_delete.html', {
        'object_name': f"Food Item '{item.name}'",
        'cancel_url': 'menu:admin_food_list'
    })


@restaurant_admin_required
def admin_food_toggle_availability(request, pk):
    """
    AJAX / POST toggle for instantaneous kitchen stock status (In Stock / Sold Out)
    and automatic timing toggle.
    """
    if request.method == 'POST':
        item = get_object_or_404(FoodItem, pk=pk)
        action = request.POST.get('action', 'toggle_stock').strip()

        if action == 'toggle_timing':
            item.auto_timing_enabled = not item.auto_timing_enabled
            item.save()
            status_text = "Auto Timing Active" if item.auto_timing_enabled else "Auto Timing Disabled (Manual Mode)"
        else:
            item.is_available = not item.is_available
            item.save()
            status_text = "In Stock" if item.is_available else "Sold Out / Out of Stock"

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('format') == 'json' or request.content_type == 'application/json':
            return JsonResponse({
                'success': True,
                'item_id': item.id,
                'name': item.name,
                'is_available': item.is_available,
                'auto_timing_enabled': item.auto_timing_enabled,
                'is_orderable': item.is_orderable,
                'status_badge': item.current_status_badge,
                'message': f"'{item.name}' is now {status_text}."
            })

        messages.success(request, f"'{item.name}' is now {status_text}.")
        return redirect('menu:admin_food_list')
    return redirect('menu:admin_food_list')


@restaurant_admin_required
def admin_quick_food_create(request):
    """
    Instant food item creation endpoint for Admin / Head Chef.
    Accepts quick JSON or standard POST form, auto-calculates 30% discount if omitted,
    and sets meal timing slots immediately.
    """
    if request.method == 'POST':
        import json
        from django.utils.text import slugify

        is_json = request.content_type == 'application/json'
        if is_json:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = {}
        else:
            data = request.POST

        name = data.get('name', '').strip()
        category_id = data.get('category_id') or data.get('category')
        price_val = data.get('price')
        discounted_price_val = data.get('discounted_price')
        food_type = data.get('food_type', FoodItem.FoodType.VEG)
        calories = data.get('calories', 350)
        protein_grams = data.get('protein_grams', 20)

        # Handle available slots
        if is_json:
            available_slots = data.get('available_slots') or ['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER']
        else:
            available_slots = request.POST.getlist('available_slots')
            if not available_slots:
                available_slots = ['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER']

        auto_timing_enabled = str(data.get('auto_timing_enabled', 'true')).lower() in ['true', '1', 'on']
        is_available = str(data.get('is_available', 'true')).lower() in ['true', '1', 'on']
        description = data.get('description', '').strip() or f"Freshly crafted super food bowl packed with nutrients and zero preservatives."

        # Validation
        if not name:
            err = "Dish name is required."
            if is_json:
                return JsonResponse({'success': False, 'message': err}, status=400)
            messages.error(request, err)
            return redirect('menu:admin_food_list')

        try:
            category = Category.objects.get(id=category_id)
        except (Category.DoesNotExist, ValueError, TypeError):
            category = Category.objects.first()
            if not category:
                category = Category.objects.create(name='Signature Bowls', slug='signature-bowls')

        try:
            price = Decimal(str(price_val))
        except (ValueError, TypeError, DecimalException):
            price = Decimal('199.00')

        if discounted_price_val:
            try:
                discounted_price = Decimal(str(discounted_price_val))
            except Exception:
                discounted_price = Decimal(round(float(price) * 0.70))
        else:
            # Represent 30% discount automatically
            discounted_price = Decimal(round(float(price) * 0.70))

        # Slug uniqueness
        base_slug = slugify(name)
        slug = base_slug
        counter = 1
        while FoodItem.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        image_file = request.FILES.get('image')

        food_item = FoodItem.objects.create(
            category=category,
            name=name,
            slug=slug,
            image=image_file,
            description=description,
            price=price,
            discounted_price=discounted_price,
            food_type=food_type,
            calories=int(calories) if str(calories).isdigit() else 350,
            protein_grams=Decimal(str(protein_grams)) if str(protein_grams).replace('.', '', 1).isdigit() else Decimal('20.0'),
            carbs_grams=Decimal('35.0'),
            fats_grams=Decimal('10.0'),
            fiber_grams=Decimal('5.0'),
            available_slots=available_slots,
            auto_timing_enabled=auto_timing_enabled,
            is_available=is_available,
            is_zero_preservative=True,
            is_high_protein=float(protein_grams) >= 25.0 if str(protein_grams).replace('.', '', 1).isdigit() else False,
        )

        success_msg = f"Super Food Dish '{food_item.name}' added instantly to the menu!"
        if is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'item_id': food_item.id,
                'name': food_item.name,
                'slug': food_item.slug,
                'price': str(food_item.price),
                'discounted_price': str(food_item.discounted_price),
                'effective_price': str(food_item.effective_price),
                'available_slots': food_item.available_slots,
                'is_available': food_item.is_available,
                'message': success_msg
            })
        messages.success(request, success_msg)
        return redirect('menu:admin_food_list')
    return redirect('menu:admin_food_list')


def food_item_customization_api(request, item_id):
    """
    Returns JSON payload of customization groups and options for an item.
    """
    food_item = get_object_or_404(FoodItem, id=item_id, is_available=True)
    groups = []
    for g in food_item.customization_groups.prefetch_related('options').all():
        options = []
        for opt in g.options.filter(is_available=True):
            options.append({
                'id': opt.id,
                'name': opt.name,
                'price_modifier': str(opt.price_modifier),
                'calories_modifier': opt.calories_modifier,
                'protein_modifier': str(opt.protein_modifier),
            })
        groups.append({
            'id': g.id,
            'name': g.name,
            'min_choices': g.min_choices,
            'max_choices': g.max_choices,
            'is_required': g.is_required,
            'options': options,
        })
    return JsonResponse({
        'success': True,
        'item': {
            'id': food_item.id,
            'name': food_item.name,
            'base_price': str(food_item.price),
            'effective_price': str(food_item.effective_price),
            'discount_percentage': food_item.discount_percentage,
            'savings_amount': str(food_item.savings_amount),
            'calories': food_item.calories,
            'protein': str(food_item.protein_grams),
            'carbs': str(food_item.carbs_grams),
            'fats': str(food_item.fats_grams),
        },
        'groups': groups,
    })
