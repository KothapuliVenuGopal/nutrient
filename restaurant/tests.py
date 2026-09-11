from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from .models import RestaurantProfile, BusinessHour


class RestaurantManagementTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='chef_admin',
            email='chef@nutrientfood.in',
            password='Password123!',
            role=User.Role.RESTAURANT_ADMIN
        )
        self.customer = User.objects.create_user(
            username='regular_customer',
            email='user@example.com',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.profile = RestaurantProfile.get_instance()

    def test_singleton_restaurant_profile(self):
        profile1 = RestaurantProfile.get_instance()
        profile2 = RestaurantProfile.get_instance()
        self.assertEqual(profile1.pk, profile2.pk)
        self.assertEqual(RestaurantProfile.objects.count(), 1)

    def test_toggle_accepting_orders_admin_only(self):
        # Customer should be redirected / denied
        self.client.login(username='regular_customer', password='Password123!')
        res_cust = self.client.post(reverse('restaurant:toggle_orders'))
        self.assertEqual(res_cust.status_code, 302)

        # Admin can toggle successfully
        self.client.login(username='chef_admin', password='Password123!')
        initial_status = self.profile.is_accepting_orders
        res_admin = self.client.post(reverse('restaurant:toggle_orders'))
        self.assertEqual(res_admin.status_code, 302)
        
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.is_accepting_orders, not initial_status)

    def test_restaurant_settings_update(self):
        self.client.login(username='chef_admin', password='Password123!')
        response = self.client.post(reverse('restaurant:settings'), {
            'name': 'Nutrient – The Super Food',
            'tagline': 'Eat Clean. Stay Strong. Live Better.',
            'secondary_tagline': 'Clean Food, Real Ingredients, Real Results',
            'description': '100% clean healthy food in Hyderabad.',
            'phone': '+91 7993476624',
            'whatsapp_number': '+91 7993476624',
            'email': 'orders@nutrientfood.in',
            'address_line': 'Madhapur, HITEC City',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500081',
            'is_accepting_orders': True,
            'min_order_value': '249.00',
            'default_delivery_charge': '45.00',
            'free_delivery_threshold': '600.00',
            'tax_percentage': '5.00',
            'delivery_radius_km': '18.0',
            'avg_preparation_time_mins': 20,
        })
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
    def test_dashboard_view_admin(self):
        self.client.login(username='chef_admin', password='Password123!')
        response = self.client.get(reverse('restaurant:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Executive Command Center')
        self.assertIn('chart_days_labels', response.context)
        self.assertIn('today_revenue', response.context)

    def test_dashboard_view_customer_forbidden(self):
        self.client.login(username='regular_customer', password='Password123!')
        response = self.client.get(reverse('restaurant:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_kitchen_orders_view(self):
        self.client.login(username='chef_admin', password='Password123!')
        response = self.client.get(reverse('restaurant:kitchen_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kitchen Display System')

    def test_assign_rider_view(self):
        from orders.models import Order
        from delivery.models import DeliveryPartnerProfile, DeliveryAssignment

        rider_user = User.objects.create_user(
            username='speedy_rider',
            email='rider@example.com',
            password='Password123!',
            role=User.Role.DELIVERY_PARTNER
        )
        rider = DeliveryPartnerProfile.objects.create(
            user=rider_user,
            vehicle_type='BIKE',
            vehicle_number='TS09AB1234',
            is_available=True
        )

        order = Order.objects.create(
            customer=self.customer,
            delivery_name='Regular Customer',
            delivery_phone='+919876543210',
            delivery_address='Flat 401, Hi-tech City',
            delivery_pincode='500081',
            subtotal=300.00,
            delivery_fee=40.00,
            tax_amount=15.00,
            discount_amount=0.00,
            total_amount=355.00,
            status=Order.Status.READY_FOR_PICKUP
        )

        self.client.login(username='chef_admin', password='Password123!')
        res = self.client.post(
            reverse('restaurant:assign_rider', kwargs={'order_number': order.order_number}),
            {'rider_id': rider.id}
        )
        self.assertEqual(res.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.OUT_FOR_DELIVERY)
        assignment = DeliveryAssignment.objects.get(order=order)
        self.assertEqual(assignment.delivery_partner, rider)
        self.assertIsNotNone(assignment.delivery_otp)

    def test_whatsapp_template_and_message_generation(self):
        from menu.models import FoodItem, Category
        from subscriptions.models import SubscriptionPlan
        from restaurant.models import WhatsAppTemplate, WhatsAppMessageLog
        from restaurant.whatsapp_service import build_welcome_whatsapp_message, dispatch_whatsapp_message

        # Set up menu item with 30% discount
        cat = Category.objects.create(name='Signature Bowls', slug='signature-protein-bowls')
        dish = FoodItem.objects.create(
            name='Veg Protein Bowl',
            category=cat,
            price=256,
            discounted_price=179,
            protein_grams=28,
            calories=380,
            is_available=True
        )

        # Set up subscription plan
        plan = SubscriptionPlan.objects.create(
            name='Veg Bowl Subscription (Weekly)',
            bowl_type=SubscriptionPlan.BowlType.VEG_PROTEIN,
            duration=SubscriptionPlan.Duration.WEEKLY,
            total_bowls=7,
            original_price=1790,
            price=1253,
            is_active=True
        )

        template = WhatsAppTemplate.get_welcome_template()
        self.assertTrue(template.is_active)

        msg = build_welcome_whatsapp_message(self.customer, template=template)
        self.assertIn("Veg Protein Bowl", msg)
        self.assertIn("₹179", msg)  # 30% discounted price
        self.assertIn("Weekly", msg)
        self.assertIn("₹1,253", msg)

        # Test dispatch
        log = dispatch_whatsapp_message('+919876543210', msg, customer=self.customer)
        self.assertEqual(log.status, WhatsAppMessageLog.Status.SENT)
        self.assertIn("https://api.whatsapp.com/send", log.wa_web_link)
        self.assertEqual(WhatsAppMessageLog.objects.count(), 1)

    def test_whatsapp_admin_settings_view(self):
        self.client.login(username='chef_admin', password='Password123!')
        res = self.client.get(reverse('restaurant:whatsapp_settings'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'WhatsApp Automation & Welcome Dispatcher')

        # Admin saves updated template
        post_res = self.client.post(reverse('restaurant:whatsapp_settings'), {
            'title': 'Updated Welcome Highlights',
            'is_active': 'on',
            'include_live_menu': 'on',
            'include_subscriptions': 'on',
            'body_text': 'Hi {customer_name}! Check out our {menu_items} and {order_link}.'
        })
        self.assertEqual(post_res.status_code, 302)

        from restaurant.models import WhatsAppTemplate
        tmpl = WhatsAppTemplate.get_welcome_template()
        self.assertEqual(tmpl.title, 'Updated Welcome Highlights')

    def test_whatsapp_test_send_view(self):
        from restaurant.models import WhatsAppMessageLog
        self.client.login(username='chef_admin', password='Password123!')
        res = self.client.post(reverse('restaurant:whatsapp_send_test'), {
            'recipient_phone': '9876543210'
        })
        self.assertEqual(res.status_code, 302)
        self.assertTrue(WhatsAppMessageLog.objects.filter(recipient_phone='9876543210').exists())


class MealWhatsAppTestCase(TestCase):
    """
    Comprehensive tests for the Every-Meal Daily WhatsApp Broadcast automation:
    - Slot templates (Breakfast, Lunch, Evening Snack, Dinner)
    - Customer profile personalization (Active subscriber vs non-subscriber, diet preference, favorite dish)
    - Live meal menu generation with 30% discount pricing
    - Dispatch engine with daily de-duplication
    - Audience segment targeting (ALL, SUBSCRIBERS, NON_SUBSCRIBERS, VEG, NON_VEG)
    - Admin control dashboard, template editor, test sender, and 1-click broadcast trigger
    - Background management command CLI execution
    """
    def setUp(self):
        from menu.models import FoodItem, Category
        from subscriptions.models import SubscriptionPlan, CustomerSubscription
        from accounts.models import Address
        from orders.models import Order, OrderItem
        from django.utils import timezone

        self.client = Client()

        # Admin user
        self.admin = User.objects.create_user(
            username='chef_master',
            email='chef_master@nutrientfood.in',
            password='Password123!',
            role=User.Role.RESTAURANT_ADMIN
        )

        # Customer 1: Active Subscriber
        self.sub_customer = User.objects.create_user(
            username='rahul_subscriber',
            email='rahul@example.com',
            phone='9876543211',
            first_name='Rahul',
            last_name='Sharma',
            password='Password123!',
            role=User.Role.CUSTOMER
        )

        # Customer 2: Non-subscribed Regular Diner
        self.diner_customer = User.objects.create_user(
            username='priya_diner',
            email='priya@example.com',
            phone='9876543212',
            first_name='Priya',
            last_name='Reddy',
            password='Password123!',
            role=User.Role.CUSTOMER
        )

        # Customer 3: Non-Veg Fitness Enthusiast with past orders
        self.non_veg_customer = User.objects.create_user(
            username='arjun_nonveg',
            email='arjun@example.com',
            phone='9876543213',
            first_name='Arjun',
            last_name='Verma',
            password='Password123!',
            role=User.Role.CUSTOMER
        )

        # Restaurant profile
        self.profile = RestaurantProfile.get_instance()

        # Menu Items
        self.cat_bowls = Category.objects.create(name='Signature Bowls', slug='signature-protein-bowls')
        self.cat_snacks = Category.objects.create(name='Snack Bowls', slug='snack-bowls')

        self.veg_dish = FoodItem.objects.create(
            name='Veg Protein Bowl',
            category=self.cat_bowls,
            food_type='VEG',
            price=256,
            discounted_price=179,
            protein_grams=28,
            available_slots=['BREAKFAST', 'LUNCH', 'DINNER'],
            is_available=True
        )

        self.chicken_dish = FoodItem.objects.create(
            name='Chicken Protein Bowl',
            category=self.cat_bowls,
            food_type='NON_VEG',
            price=356,
            discounted_price=249,
            protein_grams=44,
            available_slots=['LUNCH', 'DINNER'],
            is_available=True
        )

        self.snack_dish = FoodItem.objects.create(
            name='Roasted Makhana Bowl',
            category=self.cat_snacks,
            food_type='VEG',
            price=170,
            discounted_price=119,
            protein_grams=8,
            available_slots=['SNACK'],
            is_available=True
        )

        # Subscription Setup for sub_customer
        self.plan = SubscriptionPlan.objects.create(
            name='Veg Bowl Subscription (Weekly)',
            bowl_type=SubscriptionPlan.BowlType.VEG_PROTEIN,
            duration=SubscriptionPlan.Duration.WEEKLY,
            total_bowls=7,
            original_price=1790,
            price=1253,
            is_active=True
        )

        self.sub_addr = Address.objects.create(
            user=self.sub_customer,
            street_address='Flat 402, Green Valley',
            pincode='500081'
        )

        self.customer_subscription = CustomerSubscription.objects.create(
            user=self.sub_customer,
            plan=self.plan,
            status=CustomerSubscription.Status.ACTIVE,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timezone.timedelta(days=7),
            delivery_time_slot=CustomerSubscription.TimeSlot.LUNCH,
            delivery_address=self.sub_addr,
            bowls_total=7,
            bowls_delivered=3
        )

        # Past order for non_veg_customer
        order = Order.objects.create(
            order_number='ORD-TEST-NV-999',
            customer=self.non_veg_customer,
            delivery_name='Arjun Verma',
            delivery_phone='9876543213',
            delivery_address='HiTech City',
            delivery_pincode='500081',
            subtotal=249,
            total_amount=249,
            status=Order.Status.DELIVERED
        )
        OrderItem.objects.create(
            order=order,
            food_item=self.chicken_dish,
            food_name='Chicken Protein Bowl',
            food_type='NON_VEG',
            unit_price=249,
            quantity=2,
            subtotal=498
        )

    def test_meal_template_defaults_initialization(self):
        from restaurant.models import WhatsAppTemplate

        slots = ['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER']
        expected_times = {
            'BREAKFAST': '07:30:00',
            'LUNCH': '12:00:00',
            'SNACK': '16:30:00',
            'DINNER': '19:30:00',
        }

        for slot in slots:
            tmpl = WhatsAppTemplate.get_meal_template(slot)
            self.assertTrue(tmpl.is_active)
            self.assertEqual(str(tmpl.scheduled_time), expected_times[slot])
            self.assertIn('{customer_name}', tmpl.body_text)
            self.assertIn('{subscription_status}', tmpl.body_text)
            self.assertIn('{available_dishes}', tmpl.body_text)
            self.assertIn('{recommended_bowl}', tmpl.body_text)
            self.assertIn('{order_link}', tmpl.body_text)

    def test_customer_personalization_subscriber_vs_diner(self):
        from restaurant.whatsapp_service import build_daily_meal_whatsapp_message

        # 1. Active Subscriber message check
        sub_msg = build_daily_meal_whatsapp_message(self.sub_customer, 'LUNCH')
        self.assertIn('Rahul', sub_msg)
        self.assertIn('Your Daily Subscription Meal is Active!', sub_msg)
        self.assertIn('3/7 bowls fulfilled', sub_msg)
        self.assertIn('Lunch (12:30 PM – 01:30 PM)', sub_msg)

        # 2. Non-Subscribed Regular Diner message check
        diner_msg = build_daily_meal_whatsapp_message(self.diner_customer, 'LUNCH')
        self.assertIn('Priya', diner_msg)
        self.assertIn('Subscriber Advantage', diner_msg)
        self.assertIn('30% OFF', diner_msg)

    def test_customer_dietary_preference_and_favorite_dish(self):
        from restaurant.whatsapp_service import get_customer_profile_data, build_daily_meal_whatsapp_message

        profile_data = get_customer_profile_data(self.non_veg_customer)
        self.assertEqual(profile_data['dietary_preference'], 'NON_VEG')
        self.assertEqual(profile_data['favorite_dish'], 'Chicken Protein Bowl')
        self.assertIsNone(profile_data['active_subscription'])
        self.assertEqual(profile_data['orders_count'], 1)

        msg = build_daily_meal_whatsapp_message(self.non_veg_customer, 'DINNER')
        self.assertIn('Arjun', msg)
        self.assertIn('Chicken Protein Bowl', msg)

    def test_meal_slot_menu_summary_and_discount_pricing(self):
        from restaurant.whatsapp_service import generate_meal_slot_menu_summary

        # Snack session should include snack items with 30% discount prices
        snack_summary = generate_meal_slot_menu_summary('SNACK')
        self.assertIn('Roasted Makhana Bowl', snack_summary)
        self.assertIn('₹119', snack_summary)
        self.assertIn('~₹170~', snack_summary)

        # Breakfast session should include breakfast items
        breakfast_summary = generate_meal_slot_menu_summary('BREAKFAST')
        self.assertIn('Veg Protein Bowl', breakfast_summary)
        self.assertIn('₹179', breakfast_summary)

    def test_dispatch_meal_broadcast_and_deduplication(self):
        from restaurant.models import WhatsAppMessageLog
        from restaurant.whatsapp_service import dispatch_meal_broadcast

        # 1. First broadcast to ALL customers for LUNCH
        res = dispatch_meal_broadcast('LUNCH', audience='ALL')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(res['total_eligible'], 3)
        self.assertEqual(res['dispatched_count'], 3)
        self.assertEqual(res['skipped_count'], 0)

        # Verify logs created in database
        logs = WhatsAppMessageLog.objects.filter(message_type='MEAL_LUNCH')
        self.assertEqual(logs.count(), 3)
        for log in logs:
            self.assertEqual(log.status, WhatsAppMessageLog.Status.SENT)
            self.assertIn('https://api.whatsapp.com/send', log.wa_web_link)

        # 2. Second broadcast on the same day for LUNCH -> MUST be de-duplicated
        res2 = dispatch_meal_broadcast('LUNCH', audience='ALL')
        self.assertEqual(res2['status'], 'success')
        self.assertEqual(res2['dispatched_count'], 0)
        self.assertEqual(res2['skipped_count'], 3)
        self.assertEqual(WhatsAppMessageLog.objects.filter(message_type='MEAL_LUNCH').count(), 3)

    def test_dispatch_meal_broadcast_audience_segmentation(self):
        from restaurant.whatsapp_service import dispatch_meal_broadcast

        # Subscribers only for DINNER
        res_sub = dispatch_meal_broadcast('DINNER', audience='SUBSCRIBERS')
        self.assertEqual(res_sub['total_eligible'], 1)
        self.assertEqual(res_sub['dispatched_count'], 1)
        self.assertEqual(res_sub['logs'][0].recipient_phone, self.sub_customer.phone)

        # Non-subscribers only for BREAKFAST
        res_nonsub = dispatch_meal_broadcast('BREAKFAST', audience='NON_SUBSCRIBERS')
        self.assertEqual(res_nonsub['total_eligible'], 2)
        self.assertEqual(res_nonsub['dispatched_count'], 2)

    def test_admin_meal_broadcast_views(self):
        from restaurant.models import WhatsAppTemplate, WhatsAppMessageLog

        # 1. Regular customer forbidden / redirected
        self.client.login(username='rahul_subscriber', password='Password123!')
        res_cust = self.client.get(reverse('restaurant:meal_whatsapp_dashboard'))
        self.assertEqual(res_cust.status_code, 302)

        # 2. Admin can view dashboard with 4 meal cards
        self.client.login(username='chef_master', password='Password123!')
        res_admin = self.client.get(reverse('restaurant:meal_whatsapp_dashboard'))
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, 'Daily Every-Meal WhatsApp Automation')
        self.assertContains(res_admin, 'Morning Breakfast')
        self.assertContains(res_admin, 'Power Lunch')
        self.assertContains(res_admin, 'Evening Fitness Snack')
        self.assertContains(res_admin, 'Clean Dinner')
        self.assertEqual(len(res_admin.context['meal_cards']), 4)

        # 3. Admin can edit template for a meal session
        edit_url = reverse('restaurant:meal_whatsapp_edit', kwargs={'meal_slot': 'breakfast'})
        get_edit = self.client.get(edit_url)
        self.assertEqual(get_edit.status_code, 200)

        post_edit = self.client.post(edit_url, {
            'title': 'Morning Super Food Power Alert',
            'scheduled_time': '07:15:00',
            'target_audience': 'ALL',
            'is_active': 'on',
            'include_live_menu': 'on',
            'body_text': 'Good morning {customer_name}! Breakfast is served at {order_link}.'
        })
        self.assertEqual(post_edit.status_code, 302)

        tmpl = WhatsAppTemplate.get_meal_template('BREAKFAST')
        self.assertEqual(tmpl.title, 'Morning Super Food Power Alert')
        self.assertEqual(str(tmpl.scheduled_time), '07:15:00')

        # 4. Admin 1-Click Broadcast trigger
        broadcast_url = reverse('restaurant:meal_whatsapp_trigger_broadcast', kwargs={'meal_slot': 'lunch'})
        res_broadcast = self.client.post(broadcast_url, {'audience': 'ALL'})
        self.assertEqual(res_broadcast.status_code, 302)
        self.assertTrue(WhatsAppMessageLog.objects.filter(message_type='MEAL_LUNCH').exists())

        # 5. Admin Test Send to specific phone
        test_url = reverse('restaurant:meal_whatsapp_test_send', kwargs={'meal_slot': 'dinner'})
        res_test = self.client.post(test_url, {'recipient_phone': '9998887776'})
        self.assertEqual(res_test.status_code, 302)
        self.assertTrue(WhatsAppMessageLog.objects.filter(recipient_phone='9998887776', message_type='TEST_MEAL_DINNER').exists())

    def test_management_command_dispatch_meal_whatsapp(self):
        from django.core.management import call_command
        from io import StringIO

        # Test dry-run execution
        out = StringIO()
        call_command('dispatch_meal_whatsapp', meal='SNACK', dry_run=True, stdout=out)
        output = out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('SNACK', output)

        # Test actual CLI dispatch with audience filter
        out2 = StringIO()
        call_command('dispatch_meal_whatsapp', meal='SNACK', audience='SUBSCRIBERS', stdout=out2)
        output2 = out2.getvalue()
        self.assertIn('Broadcast Execution Completed', output2)


