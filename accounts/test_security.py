from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, Address
from orders.models import Order
from menu.models import Category, FoodItem


class SecurityAndRoleIsolationTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.customer_a = User.objects.create_user(
            username='customer_a',
            email='a@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.customer_b = User.objects.create_user(
            username='customer_b',
            email='b@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.admin_user = User.objects.create_user(
            username='head_chef',
            email='chef@nutrientfood.in',
            password='Password123!',
            role=User.Role.RESTAURANT_ADMIN
        )
        self.rider_user = User.objects.create_user(
            username='rider_raj',
            email='raj@nutrientfood.in',
            password='Password123!',
            role=User.Role.DELIVERY_PARTNER
        )

        # Order created by Customer A
        self.order_a = Order.objects.create(
            customer=self.customer_a,
            delivery_name="Customer A",
            delivery_phone="+919876543210",
            delivery_address="Madhapur, Hyderabad",
            delivery_pincode="500081",
            subtotal=Decimal("350.00"),
            delivery_fee=Decimal("40.00"),
            tax_amount=Decimal("17.50"),
            total_amount=Decimal("407.50"),
            status=Order.Status.PENDING
        )

        # Address created by Customer A
        self.address_a = Address.objects.create(
            user=self.customer_a,
            address_type=Address.AddressType.HOME,
            street_address="Street 1, Madhapur",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
            is_default=True
        )

    # =======================================================
    # 1. Anonymous Access Protection (Must redirect to Login)
    # =======================================================
    def test_anonymous_access_redirects_to_login(self):
        protected_urls = [
            reverse('accounts:profile'),
            reverse('accounts:address_list'),
            reverse('orders:checkout'),
            reverse('orders:order_list'),
            reverse('restaurant:dashboard'),
            reverse('restaurant:kitchen_orders'),
            reverse('restaurant:settings'),
            reverse('restaurant:hours'),
            reverse('menu:admin_food_list'),
            reverse('delivery:dashboard'),
            reverse('reviews:admin_reviews'),
        ]
        for url in protected_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, f"Expected 302 redirect for unauthenticated user on {url}")
            self.assertIn('/accounts/login/', response.url)

    # =======================================================
    # 2. Customer Role Isolation (Forbidden from Admin & Fleet)
    # =======================================================
    def test_customer_cannot_access_restaurant_admin(self):
        self.client.login(username='customer_a', password='Password123!')
        forbidden_urls = [
            reverse('restaurant:dashboard'),
            reverse('restaurant:kitchen_orders'),
            reverse('restaurant:settings'),
            reverse('restaurant:hours'),
            reverse('menu:admin_food_list'),
            reverse('reviews:admin_reviews'),
        ]
        for url in forbidden_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, f"Customer should not access {url}")

    def test_customer_cannot_access_delivery_portal(self):
        self.client.login(username='customer_a', password='Password123!')
        res = self.client.get(reverse('delivery:dashboard'))
        self.assertEqual(res.status_code, 302, "Customer should not access delivery portal")

    # =======================================================
    # 3. Delivery Partner Role Isolation
    # =======================================================
    def test_delivery_partner_cannot_access_restaurant_admin(self):
        self.client.login(username='rider_raj', password='Password123!')
        forbidden_urls = [
            reverse('restaurant:dashboard'),
            reverse('restaurant:kitchen_orders'),
            reverse('restaurant:settings'),
            reverse('menu:admin_food_list'),
            reverse('reviews:admin_reviews'),
        ]
        for url in forbidden_urls:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, f"Rider should not access {url}")

    # =======================================================
    # 4. Cross-Customer Authorization Isolation (IDOR Defense)
    # =======================================================
    def test_cross_customer_cannot_view_order_details(self):
        # Customer B attempts to view Customer A's order
        self.client.login(username='customer_b', password='Password123!')
        res = self.client.get(reverse('orders:order_detail', kwargs={'order_number': self.order_a.order_number}))
        # Conceals order existence with 404 Not Found
        self.assertEqual(res.status_code, 404)

    def test_cross_customer_cannot_cancel_order(self):
        # Customer B attempts to cancel Customer A's order
        self.client.login(username='customer_b', password='Password123!')
        res = self.client.post(
            reverse('orders:customer_cancel_order', kwargs={'order_number': self.order_a.order_number}),
            {'reason': 'Malicious cancellation'}
        )
        self.assertEqual(res.status_code, 404, "Customer B cancelling Customer A's order must return 404")
        self.order_a.refresh_from_db()
        self.assertEqual(self.order_a.status, Order.Status.PENDING)

    def test_cross_customer_cannot_access_tracking_api(self):
        # Customer B attempts to poll Customer A's live tracking API
        self.client.login(username='customer_b', password='Password123!')
        res = self.client.get(reverse('orders:order_tracking_api', kwargs={'order_number': self.order_a.order_number}))
        self.assertEqual(res.status_code, 403, "Tracking API must return 403 Forbidden for unauthorized user")

    def test_cross_customer_cannot_edit_or_delete_address(self):
        # Customer B attempts to edit/delete Customer A's address
        self.client.login(username='customer_b', password='Password123!')
        res_edit = self.client.get(reverse('accounts:address_update', kwargs={'pk': self.address_a.pk}))
        self.assertEqual(res_edit.status_code, 404, "Accessing another user's address must return 404")

        res_del = self.client.post(reverse('accounts:address_delete', kwargs={'pk': self.address_a.pk}))
        self.assertEqual(res_del.status_code, 404, "Deleting another user's address must return 404")
        self.assertTrue(Address.objects.filter(pk=self.address_a.pk).exists())

    # =======================================================
    # 5. CSRF Protection Verification
    # =======================================================
    def test_csrf_protection_enforced_on_mutating_requests(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.login(username='customer_a', password='Password123!')

        # POST without CSRF token must fail with 403 Forbidden
        response = csrf_client.post(
            reverse('accounts:address_create'),
            {
                'address_type': 'HOME',
                'street_address': 'Plot 99, Madhapur',
                'city': 'Hyderabad',
                'pincode': '500081'
            }
        )
        self.assertEqual(response.status_code, 403, "POST request without CSRF token must be rejected with 403")
