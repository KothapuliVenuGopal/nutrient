import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from restaurant.models import RestaurantProfile
from menu.models import Category, FoodItem
from cart.models import Cart, CartItem
from cart.utils import get_or_create_cart, get_cart_summary


class CartTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='fitness_buff',
            email='fitness@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.profile = RestaurantProfile.get_instance()
        self.profile.tax_percentage = Decimal('5.00')
        self.profile.default_delivery_charge = Decimal('40.00')
        self.profile.free_delivery_threshold = Decimal('500.00')
        self.profile.min_order_value = Decimal('199.00')
        self.profile.is_accepting_orders = True
        self.profile.save()

        self.category = Category.objects.create(name='Bowls')
        self.item1 = FoodItem.objects.create(
            category=self.category,
            name='Quinoa Power Bowl',
            price=Decimal('300.00'),
            protein_grams=Decimal('25.0'),
            calories=400,
            is_available=True
        )
        self.item2 = FoodItem.objects.create(
            category=self.category,
            name='Green Detox Salad',
            price=Decimal('250.00'),
            protein_grams=Decimal('15.0'),
            calories=220,
            is_available=True
        )

    def test_add_item_to_cart_authenticated(self):
        self.client.login(username='fitness_buff', password='Password123!')
        response = self.client.post(
            reverse('cart:cart_add'),
            json.dumps({'item_id': self.item1.id, 'quantity': 2}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['cart_total_items'], 2)
        self.assertEqual(Decimal(data['cart_subtotal']), Decimal('600.00'))

    def test_financial_calculations_free_delivery(self):
        # 2x Quinoa Bowl = ₹600 (exceeds ₹500 threshold -> Free delivery!)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, food_item=self.item1, quantity=2)

        summary = get_cart_summary(cart)
        self.assertEqual(summary['subtotal'], Decimal('600.00'))
        self.assertEqual(summary['tax_amount'], Decimal('30.00'))  # 5% of 600
        self.assertEqual(summary['delivery_fee'], Decimal('0.00'))  # Free delivery
        self.assertTrue(summary['is_free_delivery'])
        self.assertEqual(summary['total_amount'], Decimal('630.00'))

    def test_financial_calculations_with_delivery_charge(self):
        # 1x Green Detox Salad = ₹250 (< ₹500 threshold -> ₹40 delivery fee)
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, food_item=self.item2, quantity=1)

        summary = get_cart_summary(cart)
        self.assertEqual(summary['subtotal'], Decimal('250.00'))
        self.assertEqual(summary['tax_amount'], Decimal('12.50'))  # 5% of 250
        self.assertEqual(summary['delivery_fee'], Decimal('40.00'))  # Standard delivery
        self.assertFalse(summary['is_free_delivery'])
        self.assertEqual(summary['total_amount'], Decimal('302.50'))

    def test_macro_nutrition_aggregation(self):
        cart = Cart.objects.create(user=self.user)
        # 1x Quinoa (25g P, 400 kcal) + 2x Detox (15g P, 220 kcal)
        # Total Protein = 25 + 30 = 55g
        # Total Calories = 400 + 440 = 840 kcal
        CartItem.objects.create(cart=cart, food_item=self.item1, quantity=1)
        CartItem.objects.create(cart=cart, food_item=self.item2, quantity=2)

        summary = get_cart_summary(cart)
        self.assertEqual(summary['total_protein'], Decimal('55.0'))
        self.assertEqual(summary['total_calories'], 840)

    def test_update_quantity_and_remove(self):
        self.client.login(username='fitness_buff', password='Password123!')
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, food_item=self.item1, quantity=2)

        # Decrease from 2 to 1
        res = self.client.post(
            reverse('cart:cart_update'),
            json.dumps({'item_id': self.item1.id, 'action': 'decrease'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        data = res.json()
        self.assertEqual(data['item_quantity'], 1)

        # Decrease from 1 to 0 (auto-removes)
        res2 = self.client.post(
            reverse('cart:cart_update'),
            json.dumps({'item_id': self.item1.id, 'action': 'decrease'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        data2 = res2.json()
        self.assertTrue(data2['item_removed'])
        self.assertEqual(data2['cart_total_items'], 0)

    def test_cart_blocks_sold_out_item(self):
        self.item1.is_available = False
        self.item1.save()
        self.client.login(username='fitness_buff', password='Password123!')
        response = self.client.post(
            reverse('cart:cart_add'),
            json.dumps({'item_id': self.item1.id, 'quantity': 1}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Sold Out', data['message'])

    def test_cart_blocks_timed_out_item(self):
        # Item only available for a slot that is definitely not active right now
        # We can set slots to a slot and test
        self.item1.available_slots = ['NON_EXISTENT_SLOT']
        self.item1.auto_timing_enabled = True
        self.item1.save()
        self.client.login(username='fitness_buff', password='Password123!')
        response = self.client.post(
            reverse('cart:cart_add'),
            json.dumps({'item_id': self.item1.id, 'quantity': 1}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('not active during this hour', data['message'])
