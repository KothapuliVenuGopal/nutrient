from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, Address
from restaurant.models import RestaurantProfile
from menu.models import Category, FoodItem
from cart.models import Cart, CartItem
from payments.models import Payment
from delivery.models import DeliveryPartnerProfile, DeliveryAssignment
from .models import Order, OrderItem, Coupon


class OrdersWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            username='health_enthusiast',
            email='health@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.admin = User.objects.create_user(
            username='head_chef',
            email='chef@nutrientfood.in',
            password='Password123!',
            role=User.Role.RESTAURANT_ADMIN
        )
        self.driver = User.objects.create_user(
            username='fast_rider',
            email='rider@nutrientfood.in',
            password='Password123!',
            role=User.Role.DELIVERY_PARTNER
        )
        self.rider_profile = DeliveryPartnerProfile.objects.create(
            user=self.driver,
            vehicle_number='TS 09 EA 4321',
            is_available=True
        )

        self.address = Address.objects.create(
            user=self.customer,
            address_type=Address.AddressType.HOME,
            contact_name='Health Enthusiast',
            contact_phone='+919876543210',
            street_address='Road No 45, Jubilee Hills',
            city='Hyderabad',
            state='Telangana',
            pincode='500033',
            is_default=True
        )

        self.profile = RestaurantProfile.get_instance()
        self.profile.tax_percentage = Decimal('5.00')
        self.profile.default_delivery_charge = Decimal('40.00')
        self.profile.free_delivery_threshold = Decimal('500.00')
        self.profile.min_order_value = Decimal('199.00')
        self.profile.is_accepting_orders = True
        self.profile.save()

        self.category = Category.objects.create(name='Super Bowls')
        self.dish = FoodItem.objects.create(
            category=self.category,
            name='Avocado Chickpea Bowl',
            price=Decimal('250.00'),
            protein_grams=Decimal('20.0'),
            calories=350,
            is_available=True
        )

        self.coupon = Coupon.objects.create(
            code='CLEAN20',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('20.00'),
            min_order_amount=Decimal('200.00'),
            valid_from=timezone.now() - timezone.timedelta(days=1),
            valid_until=timezone.now() + timezone.timedelta(days=30),
            is_active=True
        )

    def test_checkout_requires_login(self):
        response = self.client.get(reverse('orders:checkout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_checkout_empty_cart_redirect(self):
        self.client.login(username='health_enthusiast', password='Password123!')
        response = self.client.get(reverse('orders:checkout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('menu:food_list'))

    def test_checkout_placement_cod(self):
        self.client.login(username='health_enthusiast', password='Password123!')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, food_item=self.dish, quantity=2)  # ₹500 subtotal

        response = self.client.post(reverse('orders:checkout'), {
            'address': self.address.id,
            'payment_method': Payment.Method.COD,
            'customer_notes': 'Please deliver before 8 PM',
            'coupon_code': '',
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify Order Created
        order = Order.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.subtotal, Decimal('500.00'))
        self.assertEqual(order.tax_amount, Decimal('25.00'))  # 5% of 500
        self.assertEqual(order.delivery_fee, Decimal('0.00'))  # >= 500 free delivery
        self.assertEqual(order.total_amount, Decimal('525.00'))
        self.assertEqual(order.total_protein, Decimal('40.0'))
        self.assertEqual(order.total_calories, 700)
        self.assertEqual(order.payment.payment_method, Payment.Method.COD)
        
        # Verify Cart Cleared
        self.assertEqual(cart.items.count(), 0)

    def test_checkout_placement_with_coupon_and_online_mock(self):
        self.client.login(username='health_enthusiast', password='Password123!')
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, food_item=self.dish, quantity=2)  # ₹500 subtotal

        response = self.client.post(reverse('orders:checkout'), {
            'address': self.address.id,
            'payment_method': Payment.Method.ONLINE_MOCK,
            'customer_notes': '',
            'coupon_code': 'CLEAN20',
        })
        self.assertEqual(response.status_code, 302)

        order = Order.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(order)
        # 20% of 500 = ₹100 discount
        self.assertEqual(order.discount_amount, Decimal('100.00'))
        self.assertEqual(order.total_amount, Decimal('425.00'))  # 500 + 25 - 100
        self.assertEqual(order.payment.status, Payment.Status.SUCCESS)
        self.assertEqual(order.status, Order.Status.CONFIRMED)

    def test_state_machine_legal_progression(self):
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PENDING,
            delivery_name='Health Diner',
            delivery_phone='+919876543210',
            delivery_address='Jubilee Hills, Hyderabad',
            delivery_pincode='500033',
            total_amount=Decimal('350.00')
        )
        # Legal sequence: PENDING -> CONFIRMED -> PREPARING -> READY_FOR_PICKUP -> OUT_FOR_DELIVERY -> DELIVERED
        order.transition_to(Order.Status.CONFIRMED)
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertIsNotNone(order.confirmed_at)

        order.transition_to(Order.Status.PREPARING)
        self.assertEqual(order.status, Order.Status.PREPARING)

        order.transition_to(Order.Status.READY_FOR_PICKUP)
        self.assertEqual(order.status, Order.Status.READY_FOR_PICKUP)
        self.assertIsNotNone(order.prepared_at)

        order.transition_to(Order.Status.OUT_FOR_DELIVERY)
        self.assertEqual(order.status, Order.Status.OUT_FOR_DELIVERY)
        self.assertIsNotNone(order.picked_up_at)

        order.transition_to(Order.Status.DELIVERED)
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertIsNotNone(order.delivered_at)

    def test_state_machine_illegal_transition(self):
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PENDING,
            delivery_name='Health Diner',
            delivery_phone='+919876543210',
            delivery_address='Jubilee Hills, Hyderabad',
            delivery_pincode='500033'
        )
        # Cannot jump straight from PENDING to DELIVERED
        with self.assertRaises(ValueError):
            order.transition_to(Order.Status.DELIVERED)

    def test_customer_cancellation_allowed_in_pending(self):
        self.client.login(username='health_enthusiast', password='Password123!')
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PENDING,
            delivery_name='Health Diner',
            delivery_phone='+919876543210',
            delivery_address='Jubilee Hills, Hyderabad',
            delivery_pincode='500033'
        )
        res = self.client.post(reverse('orders:customer_cancel_order', args=[order.order_number]), {
            'reason': 'Changed my mind'
        })
        self.assertEqual(res.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(order.cancellation_reason, 'Changed my mind')

    def test_customer_cancellation_denied_in_prep(self):
        self.client.login(username='health_enthusiast', password='Password123!')
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.PREPARING,
            delivery_name='Health Diner',
            delivery_phone='+919876543210',
            delivery_address='Jubilee Hills, Hyderabad',
            delivery_pincode='500033'
        )
        res = self.client.post(reverse('orders:customer_cancel_order', args=[order.order_number]))
        self.assertEqual(res.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PREPARING)  # Still preparing

    def test_customer_reorder_workflow(self):
        self.client.login(username='health_enthusiast', password='Password123!')
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.DELIVERED,
            delivery_name='Health Diner',
            delivery_phone='+919876543210',
            delivery_address='Jubilee Hills, Hyderabad',
            delivery_pincode='500033'
        )
        OrderItem.objects.create(
            order=order,
            food_item=self.dish,
            food_name=self.dish.name,
            unit_price=self.dish.price,
            quantity=2,
            subtotal=Decimal('500.00')
        )
        res = self.client.post(reverse('orders:customer_reorder', args=[order.order_number]))
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.url, reverse('cart:cart_detail'))
        
        cart = Cart.objects.get(user=self.customer)
        self.assertEqual(cart.total_items, 2)

    def test_order_tracking_api(self):
        self.client.login(username='health_enthusiast', password='Password123!')
        order = Order.objects.create(
            customer=self.customer,
            status=Order.Status.CONFIRMED,
            delivery_name='Health Diner',
            delivery_phone='+919876543210',
            delivery_address='Jubilee Hills, Hyderabad',
            delivery_pincode='500033'
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_partner=self.rider_profile
        )
        res = self.client.get(reverse('orders:order_tracking_api', args=[order.order_number]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['status'], 'CONFIRMED')
        self.assertEqual(data['delivery_otp'], assignment.delivery_otp)
        self.assertEqual(data['partner']['vehicle_number'], 'TS 09 EA 4321')
