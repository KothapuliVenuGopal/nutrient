from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from accounts.decorators import restaurant_admin_required
from menu.models import FoodItem
from orders.models import Order
from .models import Review
from .forms import ReviewForm


@require_POST
@login_required
def submit_review_view(request, food_slug):
    """
    Submits or updates a customer review for a specific super food dish.
    """
    item = get_object_or_404(FoodItem, slug=food_slug)
    form = ReviewForm(request.POST)

    if form.is_valid():
        rating = int(form.cleaned_data['rating'])
        comment = form.cleaned_data['comment'].strip()

        order_number = request.POST.get('order_number')
        order = None
        if order_number:
            order = Order.objects.filter(order_number=order_number, customer=request.user).first()

        review, created = Review.objects.update_or_create(
            customer=request.user,
            food_item=item,
            defaults={
                'rating': rating,
                'comment': comment,
                'order': order,
                'is_approved': True
            }
        )

        action_msg = "submitted" if created else "updated"
        messages.success(request, f"Thank you! Your review for '{item.name}' has been {action_msg}.")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.POST.get('format') == 'json':
            return JsonResponse({
                'success': True,
                'message': f"Review {action_msg} successfully.",
                'rating': review.rating,
                'reviewer': request.user.get_display_name()
            })

        return redirect('menu:food_detail', slug=item.slug)
    else:
        errs = form.errors.as_text()
        messages.error(request, f"Could not submit review: {errs}")
        return redirect('menu:food_detail', slug=item.slug)


@require_POST
@login_required
def submit_order_review_view(request, order_number):
    """
    Submits overall experience feedback for a delivered order.
    """
    order = get_object_or_404(Order, order_number=order_number, customer=request.user)
    form = ReviewForm(request.POST)

    if form.is_valid():
        rating = int(form.cleaned_data['rating'])
        comment = form.cleaned_data['comment'].strip()

        Review.objects.create(
            customer=request.user,
            order=order,
            rating=rating,
            comment=comment,
            is_approved=True
        )
        messages.success(request, f"Thank you for reviewing Order #{order.order_number}!")
        return redirect('orders:order_detail', order_number=order.order_number)
    else:
        messages.error(request, "Please provide a valid rating and comment.")
        return redirect('orders:order_detail', order_number=order.order_number)


@restaurant_admin_required
def admin_reviews_view(request):
    """
    Kitchen admin dashboard to monitor and moderate customer reviews.
    """
    status_filter = request.GET.get('status', 'all')
    reviews = Review.objects.select_related('customer', 'food_item', 'order').order_by('-created_at')

    if status_filter == 'approved':
        reviews = reviews.filter(is_approved=True)
    elif status_filter == 'pending':
        reviews = reviews.filter(is_approved=False)

    return render(request, 'reviews/admin_review_list.html', {
        'reviews': reviews,
        'status_filter': status_filter
    })


@require_POST
@restaurant_admin_required
def toggle_review_approval_view(request, review_id):
    """
    Toggle moderation visibility status of a review.
    """
    review = get_object_or_404(Review, id=review_id)
    review.is_approved = not review.is_approved
    review.save()

    status_str = "Approved (Visible)" if review.is_approved else "Hidden from public"
    messages.success(request, f"Review #{review.id} status: {status_str}.")
    return redirect('reviews:admin_reviews')
