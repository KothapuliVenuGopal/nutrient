from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from .models import Category, FoodItem


class MenuTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='kitchen_lead',
            email='lead@nutrientfood.in',
            password='Password123!',
            role=User.Role.RESTAURANT_ADMIN
        )
        self.customer = User.objects.create_user(
            username='diner1',
            email='diner@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.cat_bowls = Category.objects.create(name='High-Protein Bowls', display_order=1)
        self.cat_salads = Category.objects.create(name='Gourmet Salads', display_order=2)

        self.bowl1 = FoodItem.objects.create(
            category=self.cat_bowls,
            name='Tofu Quinoa Power Bowl',
            price=Decimal('349.00'),
            discounted_price=Decimal('299.00'),
            protein_grams=Decimal('28.5'),
            calories=380,
            food_type=FoodItem.FoodType.VEGAN,
            is_available=True
        )
        self.bowl2 = FoodItem.objects.create(
            category=self.cat_bowls,
            name='Grilled Chicken Super Bowl',
            price=Decimal('399.00'),
            protein_grams=Decimal('38.0'),
            calories=440,
            food_type=FoodItem.FoodType.NON_VEG,
            is_available=True,
            is_bestseller=True
        )
        self.salad1 = FoodItem.objects.create(
            category=self.cat_salads,
            name='Greek Feta Crunch Salad',
            price=Decimal('279.00'),
            protein_grams=Decimal('12.0'),
            calories=250,
            food_type=FoodItem.FoodType.VEG,
            is_available=True
        )
        self.unavailable_item = FoodItem.objects.create(
            category=self.cat_bowls,
            name='Avocado Edamame Bowl',
            price=Decimal('369.00'),
            protein_grams=Decimal('22.0'),
            calories=390,
            food_type=FoodItem.FoodType.VEGAN,
            is_available=False  # Sold out
        )

    def test_food_item_auto_tagging_and_pricing(self):
        self.assertTrue(self.bowl1.is_high_protein)
        self.assertTrue(self.bowl1.is_calorie_conscious)
        self.assertEqual(self.bowl1.effective_price, Decimal('299.00'))
        self.assertEqual(self.bowl1.discount_percentage, 14)

    def test_stock_toggle_availability(self):
        self.client.login(username='kitchen_lead', password='Password123!')
        response = self.client.post(reverse('menu:admin_food_toggle_availability', args=[self.bowl2.pk]))
        self.assertEqual(response.status_code, 302)
        self.bowl2.refresh_from_db()
        self.assertFalse(self.bowl2.is_available)

    def test_customer_cannot_access_menu_admin(self):
        self.client.login(username='diner1', password='Password123!')
        response = self.client.get(reverse('menu:admin_food_list'))
        self.assertEqual(response.status_code, 302)

    def test_customer_menu_browsing(self):
        response = self.client.get(reverse('menu:food_list'))
        self.assertEqual(response.status_code, 200)
        items = list(response.context['items'])
        # Only available items should be returned
        self.assertIn(self.bowl1, items)
        self.assertIn(self.bowl2, items)
        self.assertIn(self.salad1, items)
        self.assertNotIn(self.unavailable_item, items)

    def test_category_filtering(self):
        response = self.client.get(reverse('menu:food_list'), {'category': self.cat_salads.slug})
        self.assertEqual(response.status_code, 200)
        items = list(response.context['items'])
        self.assertIn(self.salad1, items)
        self.assertNotIn(self.bowl1, items)

    def test_diet_type_filtering(self):
        # Filter for Vegan
        response = self.client.get(reverse('menu:food_list'), {'type': 'VEGAN'})
        self.assertEqual(response.status_code, 200)
        items = list(response.context['items'])
        self.assertIn(self.bowl1, items)
        self.assertNotIn(self.bowl2, items)

    def test_health_tag_filtering(self):
        # Filter for high protein
        response = self.client.get(reverse('menu:food_list'), {'tag': 'high_protein'})
        self.assertEqual(response.status_code, 200)
        items = list(response.context['items'])
        self.assertIn(self.bowl1, items)
        self.assertIn(self.bowl2, items)
        self.assertNotIn(self.salad1, items)

    def test_search_filtering(self):
        response = self.client.get(reverse('menu:food_list'), {'q': 'Chicken'})
        self.assertEqual(response.status_code, 200)
        items = list(response.context['items'])
        self.assertIn(self.bowl2, items)
        self.assertNotIn(self.bowl1, items)

    def test_sorting_engine(self):
        # Sort by highest protein
        response = self.client.get(reverse('menu:food_list'), {'sort': 'protein_desc'})
        self.assertEqual(response.status_code, 200)
        items = list(response.context['items'])
        self.assertEqual(items[0], self.bowl2)  # 38g protein is highest

    def test_food_detail_view(self):
        response = self.client.get(reverse('menu:food_detail', args=[self.bowl1.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['item'], self.bowl1)
        self.assertGreater(response.context['protein_ratio'], 0)

    def test_customization_api(self):
        from .models import CustomizationGroup, CustomizationOption
        group = CustomizationGroup.objects.create(
            food_item=self.bowl1,
            name="Protein Sources",
            min_choices=1,
            max_choices=2,
            is_required=True
        )
        opt1 = CustomizationOption.objects.create(
            group=group,
            name="Paneer Cubes",
            price_modifier=Decimal('0.00'),
            display_order=1
        )
        opt2 = CustomizationOption.objects.create(
            group=group,
            name="Tofu",
            price_modifier=Decimal('0.00'),
            display_order=2
        )
        self.assertTrue(self.bowl1.is_customizable)
        self.assertEqual(self.bowl1.savings_amount, Decimal('50.00'))

        response = self.client.get(reverse('menu:item_customization_api', args=[self.bowl1.pk]))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['item']['name'], self.bowl1.name)
        self.assertEqual(len(data['groups']), 1)
        self.assertEqual(data['groups'][0]['name'], "Protein Sources")
        self.assertEqual(len(data['groups'][0]['options']), 2)

    def test_seed_nutrient_data_command(self):
        from django.core.management import call_command
        from orders.models import Coupon
        from delivery.models import DeliveryPartnerProfile

        call_command('seed_nutrient_data')
        self.assertTrue(Category.objects.filter(slug='signature-protein-bowls').exists())
        self.assertTrue(FoodItem.objects.filter(slug='veg-protein-bowl').exists())
        self.assertTrue(Coupon.objects.filter(code='CLEAN20').exists())
        self.assertTrue(DeliveryPartnerProfile.objects.filter(user__username='rider_rajesh').exists())

    def test_get_current_meal_slot(self):
        from menu.views import get_current_meal_slot
        slot = get_current_meal_slot()
        self.assertIn(slot['code'], ['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER', 'CLOSED'])
        self.assertIn('timing', slot)

    def test_meal_slot_activation(self):
        import datetime
        item = FoodItem.objects.create(
            category=self.cat_bowls,
            name='Morning Power Oats Bowl',
            price=Decimal('199.00'),
            available_slots=['BREAKFAST'],
            auto_timing_enabled=True,
            is_available=True
        )
        # 08:30 AM should be active for BREAKFAST (07:00 - 11:30)
        t_breakfast = datetime.time(8, 30)
        self.assertTrue(item.is_slot_active(current_time=t_breakfast))

        # 02:00 PM should be inactive for BREAKFAST
        t_lunch = datetime.time(14, 0)
        self.assertFalse(item.is_slot_active(current_time=t_lunch))

    def test_admin_quick_food_create(self):
        self.client.login(username='kitchen_lead', password='Password123!')
        response = self.client.post(
            reverse('menu:admin_quick_food_create'),
            {
                'name': 'Chef Special Sprout Protein Mix',
                'category_id': self.cat_bowls.id,
                'price': '200',
                'food_type': 'VEG',
                'calories': '320',
                'protein_grams': '22.0',
                'available_slots': ['BREAKFAST', 'SNACK'],
                'auto_timing_enabled': 'true',
                'is_available': 'true'
            }
        )
        self.assertEqual(response.status_code, 302)
        created_item = FoodItem.objects.get(name='Chef Special Sprout Protein Mix')
        self.assertEqual(created_item.price, Decimal('200'))
        # Auto 30% discount calculation -> 70% of 200 = 140
        self.assertEqual(created_item.discounted_price, Decimal('140'))
        self.assertEqual(created_item.available_slots, ['BREAKFAST', 'SNACK'])
        self.assertTrue(created_item.auto_timing_enabled)
        self.assertTrue(created_item.is_available)

    def test_admin_toggle_stock_and_timing_ajax(self):
        self.client.login(username='kitchen_lead', password='Password123!')
        # Toggle stock
        response = self.client.post(
            reverse('menu:admin_food_toggle_availability', args=[self.bowl1.id]),
            {'action': 'toggle_stock'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['is_available'])
        self.bowl1.refresh_from_db()
        self.assertFalse(self.bowl1.is_available)

        # Toggle auto timing
        response = self.client.post(
            reverse('menu:admin_food_toggle_availability', args=[self.bowl1.id]),
            {'action': 'toggle_timing'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['auto_timing_enabled'])
        self.bowl1.refresh_from_db()
        self.assertFalse(self.bowl1.auto_timing_enabled)
