from decimal import Decimal
from datetime import timedelta
import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, Address
from menu.models import Category, FoodItem, CustomizationGroup, CustomizationOption
from subscriptions.models import SubscriptionPlan, CustomerSubscription, DailySubscriptionDelivery


class SubscriptionsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            username='health_user',
            email='health@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.address = Address.objects.create(
            user=self.customer,
            address_type=Address.AddressType.HOME,
            contact_name="Health User",
            contact_phone="+91 9876543210",
            apartment_flat="Apt 402, Green Meadows",
            street_address="Madhapur Main Road",
            landmark="Near Metro Station (Within 3km)",
            city="Hyderabad",
            state="Telangana",
            pincode="500081",
            is_default=True
        )
        self.category = Category.objects.create(
            name="Signature Protein Bowls",
            slug="signature-protein-bowls"
        )
        self.food_item = FoodItem.objects.create(
            category=self.category,
            name="Veg Protein Bowl",
            slug="veg-protein-bowl",
            price=Decimal("259.00"),            # MRP
            discounted_price=Decimal("179.00"), # 70% price (30% OFF)
            protein_grams=Decimal("32.0"),
            calories=390,
            food_type=FoodItem.FoodType.VEG,
            is_available=True
        )
        # Customization groups
        self.group_protein = CustomizationGroup.objects.create(
            food_item=self.food_item,
            name="Protein Sources",
            min_choices=1,
            max_choices=2,
            is_required=True
        )
        self.opt_paneer = CustomizationOption.objects.create(
            group=self.group_protein,
            name="Grilled Paneer",
            price_modifier=Decimal("0.00"),
            display_order=1
        )
        self.opt_tofu = CustomizationOption.objects.create(
            group=self.group_protein,
            name="Organic Tofu",
            price_modifier=Decimal("0.00"),
            display_order=2
        )

        # Weekly Plan (7 Bowls)
        self.weekly_plan = SubscriptionPlan.objects.create(
            name="Veg Protein Bowl - Weekly (7 Bowls)",
            slug="veg-protein-bowl-weekly",
            bowl_type=SubscriptionPlan.BowlType.VEG_PROTEIN,
            duration=SubscriptionPlan.Duration.WEEKLY,
            total_bowls=7,
            original_price=Decimal("1813.00"),
            price=Decimal("1249.00"),
            discount_percentage=31,
            description="7 bowls of Veg Protein + dressing + super drink",
            is_active=True
        )

        # Monthly Plan (30 Bowls)
        self.monthly_plan = SubscriptionPlan.objects.create(
            name="Veg Protein Bowl - Monthly (30 Bowls)",
            slug="veg-protein-bowl-monthly",
            bowl_type=SubscriptionPlan.BowlType.VEG_PROTEIN,
            duration=SubscriptionPlan.Duration.MONTHLY,
            total_bowls=30,
            original_price=Decimal("7770.00"),
            price=Decimal("4999.00"),
            discount_percentage=36,
            description="30 bowls of Veg Protein + dressing + super drink",
            is_active=True
        )

    def test_subscription_plan_financials_and_discount(self):
        # 30% discount checks
        self.assertEqual(self.weekly_plan.discount_percentage, 31)
        self.assertEqual(self.weekly_plan.savings_amount, Decimal("564.00"))
        self.assertEqual(self.weekly_plan.price_per_bowl, Decimal("178.43"))

        self.assertEqual(self.monthly_plan.discount_percentage, 36)
        self.assertEqual(self.monthly_plan.savings_amount, Decimal("2771.00"))
        self.assertEqual(self.monthly_plan.price_per_bowl, Decimal("166.63"))

    def test_plans_catalog_view(self):
        response = self.client.get(reverse('subscriptions:plans'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Veg Protein Bowl - Weekly")
        self.assertContains(response, "Veg Protein Bowl - Monthly")
        self.assertContains(response, "30% OFF")

    def test_customer_subscribe_get_and_post(self):
        self.client.login(username='health_user', password='Password123!')
        
        # GET subscribe page
        response = self.client.get(reverse('subscriptions:subscribe', args=[self.weekly_plan.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['plan'], self.weekly_plan)

        # POST subscribe creation
        start_date = (timezone.localdate() + timedelta(days=1)).strftime('%Y-%m-%d')
        post_data = {
            'start_date': start_date,
            'time_slot': CustomerSubscription.TimeSlot.LUNCH,
            'address_id': self.address.id,
            'special_instructions': "Ring bell twice",
            'custom_Protein Sources': [self.opt_paneer.name]
        }
        response = self.client.post(reverse('subscriptions:subscribe', args=[self.weekly_plan.id]), data=post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('subscriptions:my_subscriptions'))

        # Verify subscription was created with 7 scheduled daily deliveries
        sub = CustomerSubscription.objects.get(user=self.customer, plan=self.weekly_plan)
        self.assertEqual(sub.bowls_total, 7)
        self.assertEqual(sub.bowls_delivered, 0)
        self.assertEqual(sub.daily_deliveries.count(), 7)

        # Check default customization
        self.assertIn("Protein Sources", sub.default_customization.get('selected_options', {}))
        self.assertEqual(sub.default_customization['selected_options']['Protein Sources'], [self.opt_paneer.name])

    def test_customize_daily_meal_ajax(self):
        self.client.login(username='health_user', password='Password123!')
        
        # Create subscription
        start = timezone.localdate() + timedelta(days=1)
        sub = CustomerSubscription.objects.create(
            user=self.customer,
            plan=self.weekly_plan,
            start_date=start,
            end_date=start + timedelta(days=6),
            delivery_time_slot=CustomerSubscription.TimeSlot.LUNCH,
            delivery_address=self.address,
            bowls_total=7,
            default_customization={'selected_options': {'Protein Sources': [self.opt_paneer.name]}}
        )
        first_delivery = DailySubscriptionDelivery.objects.create(
            subscription=sub,
            delivery_date=start,
            time_slot=CustomerSubscription.TimeSlot.LUNCH,
            status=DailySubscriptionDelivery.Status.SCHEDULED,
            customization={}
        )

        # Update customization for day 1 via AJAX
        url = reverse('subscriptions:customize_daily_meal', args=[first_delivery.id])
        payload = {
            'customizations': {
                'selected_options': {
                    'Protein Sources': [self.opt_tofu.name]
                }
            },
            'delivery_notes': 'Extra crispy please'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        res_json = response.json()
        self.assertTrue(res_json['success'])

        # Reload delivery
        first_delivery.refresh_from_db()
        self.assertEqual(first_delivery.delivery_notes, 'Extra crispy please')
        self.assertEqual(first_delivery.customization['selected_options']['Protein Sources'], [self.opt_tofu.name])
        self.assertIn(f"Protein Sources: {self.opt_tofu.name}", first_delivery.customization_summary)

    def test_toggle_pause_subscription_ajax(self):
        self.client.login(username='health_user', password='Password123!')
        start = timezone.localdate() + timedelta(days=1)
        sub = CustomerSubscription.objects.create(
            user=self.customer,
            plan=self.weekly_plan,
            start_date=start,
            end_date=start + timedelta(days=6),
            delivery_time_slot=CustomerSubscription.TimeSlot.LUNCH,
            delivery_address=self.address,
            bowls_total=7
        )
        self.assertFalse(sub.is_paused)

        url = reverse('subscriptions:toggle_pause', args=[sub.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        sub.refresh_from_db()
        self.assertTrue(sub.is_paused)
        self.assertEqual(sub.status, CustomerSubscription.Status.PAUSED)

        # Toggle back to resume
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        sub.refresh_from_db()
        self.assertFalse(sub.is_paused)
        self.assertEqual(sub.status, CustomerSubscription.Status.ACTIVE)
