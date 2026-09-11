from django.test import TestCase, Client, override_settings
from django.urls import reverse
from .models import User, Address


class AccountsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            username='customer1',
            email='customer1@example.com',
            password='Password123!',
            phone='+919876543210',
            role=User.Role.CUSTOMER
        )
        self.admin_user = User.objects.create_user(
            username='admin1',
            email='admin1@example.com',
            password='Password123!',
            phone='+917993476624',
            role=User.Role.RESTAURANT_ADMIN
        )
        self.driver_user = User.objects.create_user(
            username='driver1',
            email='driver1@example.com',
            password='Password123!',
            phone='+919876543299',
            role=User.Role.DELIVERY_PARTNER
        )

    def test_customer_role_properties(self):
        self.assertTrue(self.customer.is_customer)
        self.assertFalse(self.customer.is_restaurant_admin)
        self.assertFalse(self.customer.is_delivery_partner)

        self.assertTrue(self.admin_user.is_restaurant_admin)
        self.assertTrue(self.driver_user.is_delivery_partner)

    def test_customer_registration(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newcustomer',
            'first_name': 'Aarav',
            'last_name': 'Sharma',
            'email': 'aarav@example.com',
            'phone': '+919999888877',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })
        self.assertEqual(response.status_code, 302)
        created_user = User.objects.get(username='newcustomer')
        self.assertEqual(created_user.role, User.Role.CUSTOMER)
        self.assertEqual(created_user.first_name, 'Aarav')

    def test_address_management_and_default_toggle(self):
        self.client.login(username='customer1', password='Password123!')
        
        # Create 1st address (should be default)
        addr1 = Address.objects.create(
            user=self.customer,
            address_type=Address.AddressType.HOME,
            street_address='Road No 36, Jubilee Hills',
            city='Hyderabad',
            state='Telangana',
            pincode='500033',
            is_default=True
        )
        self.assertTrue(addr1.is_default)

        # Create 2nd address marked as default -> addr1 must be updated to False
        addr2 = Address.objects.create(
            user=self.customer,
            address_type=Address.AddressType.WORK,
            street_address='Cyber Towers, HITEC City',
            city='Hyderabad',
            state='Telangana',
            pincode='500081',
            is_default=True
        )
        addr1.refresh_from_db()
        self.assertFalse(addr1.is_default)
        self.assertTrue(addr2.is_default)

    def test_role_access_decorator(self):
        # Customer trying to access restaurant admin dashboard
        self.client.login(username='customer1', password='Password123!')
        response = self.client.get(reverse('restaurant:dashboard'))
        self.assertEqual(response.status_code, 302)

        # Restaurant Admin accessing restaurant admin dashboard
        self.client.login(username='admin1', password='Password123!')
        response = self.client.get(reverse('restaurant:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_phone_normalization(self):
        from accounts.otp_service import normalize_phone
        self.assertEqual(normalize_phone('9876543210'), '+919876543210')
        self.assertEqual(normalize_phone('+91 98765 43210'), '+919876543210')
        self.assertEqual(normalize_phone('09876543210'), '+919876543210')
        self.assertEqual(normalize_phone('+919876543210'), '+919876543210')

        with self.assertRaises(ValueError):
            normalize_phone('12345')  # Too short
        with self.assertRaises(ValueError):
            normalize_phone('2876543210')  # Doesn't start with 6-9

    @override_settings(DEBUG=True)
    def test_otp_generation_and_rate_limiting(self):
        from accounts.models import PhoneOTP
        # Step 1: Request OTP
        res = self.client.post(reverse('accounts:send_otp'), {'phone': '9876543210'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIsNotNone(data['dev_otp'])

        # DB record must exist
        otp_obj = PhoneOTP.objects.filter(phone='+919876543210').first()
        self.assertIsNotNone(otp_obj)
        self.assertEqual(len(otp_obj.otp_code), 6)

        # Immediate repeat should be blocked by 60s cooldown
        repeat_res = self.client.post(reverse('accounts:send_otp'), {'phone': '9876543210'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        repeat_data = repeat_res.json()
        self.assertFalse(repeat_data['success'])
        self.assertIn("Please wait", repeat_data['message'])

    def test_otp_verification_auto_creates_customer(self):
        from accounts.models import PhoneOTP
        test_phone = '9123456789'
        norm_phone = '+919123456789'

        # Generate OTP
        self.client.post(reverse('accounts:send_otp'), {'phone': test_phone}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        otp_rec = PhoneOTP.objects.get(phone=norm_phone)

        # Verify OTP with name
        verify_res = self.client.post(
            reverse('accounts:verify_otp'),
            {'phone': test_phone, 'otp_code': otp_rec.otp_code, 'first_name': 'Priya Patel'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(verify_res.status_code, 200)
        verify_data = verify_res.json()
        self.assertTrue(verify_data['success'])
        self.assertTrue(verify_data['is_new_user'])

        # Check user in database
        created_user = User.objects.get(phone=norm_phone)
        self.assertEqual(created_user.first_name, 'Priya Patel')
        self.assertEqual(created_user.role, User.Role.CUSTOMER)

    def test_otp_attempts_and_lockout(self):
        from accounts.models import PhoneOTP
        test_phone = '9876500000'
        norm_phone = '+919876500000'

        self.client.post(reverse('accounts:send_otp'), {'phone': test_phone}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        otp_rec = PhoneOTP.objects.get(phone=norm_phone)

        # Wrong code 5 times
        for i in range(5):
            res = self.client.post(
                reverse('accounts:verify_otp'),
                {'phone': test_phone, 'otp_code': '000000'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(res.status_code, 400)

        otp_rec.refresh_from_db()
        self.assertEqual(otp_rec.attempts, 5)

        # 6th attempt should return locked
        res6 = self.client.post(
            reverse('accounts:verify_otp'),
            {'phone': test_phone, 'otp_code': otp_rec.otp_code},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res6.status_code, 400)
        self.assertIn("locked", res6.json()['message'].lower())

    def test_guest_cart_transferred_on_otp_login(self):
        from accounts.models import PhoneOTP
        from cart.models import Cart, CartItem
        from menu.models import FoodItem, Category

        cat = Category.objects.create(name='Bowls', slug='test-bowls')
        dish = FoodItem.objects.create(
            name='Keto Power Bowl',
            category=cat,
            price=249,
            discounted_price=174,
            protein_grams=35,
            calories=420,
            is_available=True
        )

        # Initialize session on test client
        session = self.client.session
        session['cart_initialized'] = True
        session.save()
        session_key = session.session_key

        guest_cart = Cart.objects.create(session_key=session_key)
        CartItem.objects.create(cart=guest_cart, food_item=dish, quantity=2)

        # Now login via OTP
        test_phone = '9988776655'
        self.client.post(reverse('accounts:send_otp'), {'phone': test_phone}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        otp_rec = PhoneOTP.objects.get(phone='+919988776655')

        verify_res = self.client.post(
            reverse('accounts:verify_otp'),
            {'phone': test_phone, 'otp_code': otp_rec.otp_code},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(verify_res.status_code, 200)

        # Cart should now be assigned to user
        user = User.objects.get(phone='+919988776655')
        user_cart = Cart.objects.get(user=user)
        self.assertEqual(user_cart.items.count(), 1)
        self.assertEqual(user_cart.items.first().quantity, 2)
        # Guest cart should be deleted
        self.assertFalse(Cart.objects.filter(session_key=session_key).exists())


