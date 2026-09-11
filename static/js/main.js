/**
 * Nutrient – The Super Food
 * Dynamic Interactive Shopping Cart & UI Scripts
 */

// Helper to retrieve CSRF token from cookies
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Show a floating toast notification
function showNutrientToast(message, type = 'success') {
    let toastContainer = document.getElementById('nutrient-toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'nutrient-toast-container';
        toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '1090';
        document.body.appendChild(toastContainer);
    }

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white bg-dark-navy border-0 shadow-lg show mb-2`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    
    const icon = type === 'success' 
        ? '<i class="fa-solid fa-circle-check text-success fs-5 me-2"></i>' 
        : '<i class="fa-solid fa-triangle-exclamation text-warning fs-5 me-2"></i>';

    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body d-flex align-items-center">
                ${icon}
                <div>${message}</div>
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;

    toastContainer.appendChild(toastEl);
    setTimeout(() => {
        toastEl.classList.remove('show');
        setTimeout(() => toastEl.remove(), 300);
    }, 3500);
}

// Global dynamic Add-to-Cart handler
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.add-to-cart-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const itemId = this.getAttribute('data-item-id');
            const itemName = this.getAttribute('data-item-name') || 'Item';
            
            // Check if there's a custom quantity input on the page (e.g. food detail page)
            const detailQtyInput = document.getElementById('detail-quantity');
            const quantity = detailQtyInput ? parseInt(detailQtyInput.value) || 1 : 1;

            const originalHtml = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span> Adding...';
            this.disabled = true;

            const csrftoken = getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value;

            fetch('/cart/add/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({
                    item_id: itemId,
                    quantity: quantity
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    // Update global desktop cart badge
                    const cartBadge = document.getElementById('cart-badge');
                    if (cartBadge) {
                        cartBadge.textContent = data.cart_total_items;
                    }

                    // Update mobile cart floater
                    const mobileCartBadge = document.getElementById('mobile-cart-badge');
                    if (mobileCartBadge) {
                        mobileCartBadge.textContent = data.cart_total_items;
                    }
                    const mobileFloater = document.getElementById('mobile-cart-floater');
                    if (mobileFloater) {
                        mobileFloater.classList.remove('d-none');
                    }

                    // Floating toast feedback
                    showNutrientToast(`Added ${quantity}x ${itemName} to your super food cart! (₹${data.total_amount})`);

                    // Temporary success state on button
                    this.innerHTML = '<i class="fa-solid fa-check me-1"></i> Added';
                    this.classList.replace('btn-nutrient', 'btn-success');

                    setTimeout(() => {
                        this.innerHTML = originalHtml;
                        this.classList.replace('btn-success', 'btn-nutrient');
                        this.disabled = false;
                    }, 1500);
                } else {
                    showNutrientToast(data.message || 'Unable to add item to cart', 'warning');
                    this.innerHTML = originalHtml;
                    this.disabled = false;
                }
            })
            .catch(err => {
                console.error('Add to cart error:', err);
                showNutrientToast('An error occurred. Please try again.', 'warning');
                this.innerHTML = originalHtml;
                this.disabled = false;
            });
        });
    });
});
