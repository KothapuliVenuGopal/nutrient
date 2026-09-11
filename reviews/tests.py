from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from menu.models import Category, FoodItem
from orders.models import Coupon, Order
from .models import Review


class ReviewsAndCouponsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.customer = User.objects.create_user(
            username='fitness_pro',
            email='fit@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.admin = User.objects.create_user(
            username='chef_admin',
            email='chef@nutrientfood.in',
            password='Password123!',
            role=User.Role.RESTAURANT_ADMIN
        )

        # Menu Category and Food Item
        self.category = Category.objects.create(
            name='High-Protein Bowls',
            slug='high-protein-bowls',
            display_order=1
        )
        self.dish = FoodItem.objects.create(
            name='Super Quinoa Protein Bowl',
            slug='super-quinoa-protein-bowl',
            category=self.category,
            food_type=FoodItem.FoodType.VEG,
            price=Decimal('280.00'),
            calories=380,
            protein_grams=Decimal('28.0'),
            carbs_grams=Decimal('42.0'),
            fats_grams=Decimal('8.0'),
            fiber_grams=Decimal('9.0'),
            is_high_protein=True,
            is_available=True
        )

        # Coupons
        self.coupon_percent = Coupon.objects.create(
            code='CLEAN20',
            description='20% off clean super meals',
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('20.00'),
            min_order_amount=Decimal('200.00'),
            max_discount_amount=Decimal('80.00'),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True
        )
        self.coupon_fixed = Coupon.objects.create(
            code='HIGHPROTEIN',
            description='Flat ₹50 off on high-protein orders',
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=Decimal('50.00'),
            min_order_amount=Decimal('300.00'),
            valid_from=timezone.now() - timedelta(days=1),
            valid_until=timezone.now() + timedelta(days=30),
            is_active=True
        )

    def test_submit_dish_review_authenticated(self):
        self.client.login(username='fitness_pro', password='Password123!')
        response = self.client.post(
            reverse('reviews:submit_review', kwargs={'food_slug': self.dish.slug}),
            {
                'rating': 5,
                'comment': 'Incredible macro balance, quinoa is fluffy and fresh ingredients!'
            }
        )
        self.assertEqual(response.status_code, 302)

        review = Review.objects.get(customer=self.customer, food_item=self.dish)
        self.assertEqual(review.rating, 5)
        self.assertTrue(review.is_approved)

        # Updating existing review
        res_update = self.client.post(
            reverse('reviews:submit_review', kwargs={'food_slug': self.dish.slug}),
            {
                'rating': 4,
                'comment': 'Updated review: Still delicious, slightly less dressing preferred.'
            }
        )
        self.assertEqual(res_update.status_code, 302)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)
        self.assertEqual(Review.objects.count(), 1)

    def test_submit_dish_review_unauthenticated(self):
        response = self.client.post(
            reverse('reviews:submit_review', kwargs={'food_slug': self.dish.slug}),
            {'rating': 5, 'comment': 'Great meal!'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_admin_review_moderation(self):
        Review.objects.create(
            customer=self.customer,
            food_item=self.dish,
            rating=5,
            comment='Super tasty!',
            is_approved=True
        )
        review = Review.objects.first()

        # Customer cannot access moderation
        self.client.login(username='fitness_pro', password='Password123!')
        res_cust = self.client.get(reverse('reviews:admin_reviews'))
        self.assertEqual(res_cust.status_code, 302)

        # Admin can view and toggle approval
        self.client.login(username='chef_admin', password='Password123!')
        res_admin = self.client.get(reverse('reviews:admin_reviews'))
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, 'Super Quinoa Protein Bowl')

        # Toggle approval to False
        res_toggle = self.client.post(reverse('reviews:toggle_approval', kwargs={'review_id': review.id}))
        self.assertEqual(res_toggle.status_code, 302)
        review.refresh_from_db()
        self.assertFalse(review.is_approved)

    def test_food_detail_aggregates_reviews(self):
        # Create 2 approved reviews
        Review.objects.create(
            customer=self.customer,
            food_item=self.dish,
            rating=5,
            comment='Reviewer 1: Best clean food in HITEC city!',
            is_approved=True
        )
        another_user = User.objects.create_user(
            username='marathon_runner',
            email='run@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        Review.objects.create(
            customer=another_user,
            food_item=self.dish,
            rating=4,
            comment='Reviewer 2: Solid fuel before long runs.',
            is_approved=True
        )

        response = self.client.get(reverse('menu:food_detail', kwargs={'slug': self.dish.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['avg_rating'], 4.5)
        self.assertEqual(response.context['reviews_count'], 2)
        self.assertContains(response, 'Best clean food in HITEC city!')
        self.assertContains(response, 'Solid fuel before long runs.')

    def test_coupon_engine_validation_and_calculation(self):
        # 1. Percentage Coupon CLEAN20 (20% off, min 200, cap 80)
        # Order subtotal = 300 -> 20% of 300 = 60 <= 80 cap -> Discount = 60
        is_ok, msg = self.coupon_percent.is_valid(Decimal('300.00'))
        self.assertTrue(is_ok)
        discount = self.coupon_percent.calculate_discount(Decimal('300.00'))
        self.assertEqual(discount, Decimal('60.00'))

        # Subtotal below minimum order (150 < 200)
        is_ok_fail, msg_fail = self.coupon_percent.is_valid(Decimal('150.00'))
        self.assertFalse(is_ok_fail)
        self.assertIn('Minimum order', msg_fail)

        # Order subtotal = 500 -> 20% of 500 = 100 > cap 80 -> Discount capped at 80
        discount_capped = self.coupon_percent.calculate_discount(Decimal('500.00'))
        self.assertEqual(discount_capped, Decimal('80.00'))

        # 2. Fixed Coupon HIGHPROTEIN (Flat 50 off, min 300)
        is_ok_fixed, _ = self.coupon_fixed.is_valid(Decimal('350.00'))
        self.assertTrue(is_ok_fixed)
        discount_fixed = self.coupon_fixed.calculate_discount(Decimal('350.00'))
        self.assertEqual(discount_fixed, Decimal('50.00'))
