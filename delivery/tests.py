from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from orders.models import Order
from payments.models import Payment
from .models import DeliveryPartnerProfile, DeliveryAssignment


class DeliveryPartnerTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.customer = User.objects.create_user(
            username='health_enthusiast',
            email='user@nutrientfood.in',
            password='Password123!',
            role=User.Role.CUSTOMER
        )
        self.rider_user = User.objects.create_user(
            username='speedy_rider',
            email='rider@nutrientfood.in',
            password='Password123!',
            role=User.Role.DELIVERY_PARTNER
        )
        self.rider_profile = DeliveryPartnerProfile.objects.create(
            user=self.rider_user,
            vehicle_type=DeliveryPartnerProfile.VehicleType.EV_BIKE,
            vehicle_number='TS09-EV-2026',
            is_available=True
        )

    def test_dashboard_access_by_role(self):
        # Customer should be denied/redirected
        self.client.login(username='health_enthusiast', password='Password123!')
        res_cust = self.client.get(reverse('delivery:dashboard'))
        self.assertEqual(res_cust.status_code, 302)

        # Delivery Partner should have full access
        self.client.login(username='speedy_rider', password='Password123!')
        res_rider = self.client.get(reverse('delivery:dashboard'))
        self.assertEqual(res_rider.status_code, 200)
        self.assertContains(res_rider, 'Delivery Partner Portal')
        self.assertContains(res_rider, 'TS09-EV-2026')
        self.assertIn('active_assignments', res_rider.context)

    def test_toggle_availability(self):
        self.client.login(username='speedy_rider', password='Password123!')
        self.assertTrue(self.rider_profile.is_available)

        # Toggle to Offline
        response = self.client.post(reverse('delivery:toggle_availability'))
        self.assertEqual(response.status_code, 302)
        self.rider_profile.refresh_from_db()
        self.assertFalse(self.rider_profile.is_available)

        # Toggle back to Online
        self.client.post(reverse('delivery:toggle_availability'))
        self.rider_profile.refresh_from_db()
        self.assertTrue(self.rider_profile.is_available)

    def test_assignment_lifecycle_and_otp_verification(self):
        order = Order.objects.create(
            customer=self.customer,
            delivery_name='Health Enthusiast',
            delivery_phone='+919988776655',
            delivery_address='Flat 202, Bio Greens, Madhapur',
            delivery_pincode='500081',
            subtotal=Decimal('350.00'),
            delivery_fee=Decimal('40.00'),
            tax_amount=Decimal('17.50'),
            discount_amount=Decimal('0.00'),
            total_amount=Decimal('407.50'),
            status=Order.Status.READY_FOR_PICKUP
        )
        payment = Payment.objects.create(
            order=order,
            payment_method=Payment.Method.COD,
            status=Payment.Status.PENDING,
            amount=Decimal('407.50')
        )
        assignment = DeliveryAssignment.objects.create(
            order=order,
            delivery_partner=self.rider_profile,
            status=DeliveryAssignment.AssignmentStatus.ASSIGNED
        )
        self.assertIsNotNone(assignment.delivery_otp)
        self.assertEqual(len(assignment.delivery_otp), 4)

        self.client.login(username='speedy_rider', password='Password123!')

        # 1. Accept Assignment
        res_accept = self.client.post(reverse('delivery:accept_assignment', kwargs={'assignment_id': assignment.id}))
        self.assertEqual(res_accept.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.AssignmentStatus.ACCEPTED)

        # 2. Pick Up Assignment
        res_pickup = self.client.post(reverse('delivery:pickup_assignment', kwargs={'assignment_id': assignment.id}))
        self.assertEqual(res_pickup.status_code, 302)
        assignment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.AssignmentStatus.PICKED_UP)
        self.assertEqual(order.status, Order.Status.OUT_FOR_DELIVERY)

        # 3. Complete Delivery with Incorrect OTP (Should Fail)
        res_wrong_otp = self.client.post(
            reverse('delivery:complete_delivery', kwargs={'assignment_id': assignment.id}),
            {'delivery_otp': '0000'}
        )
        self.assertEqual(res_wrong_otp.status_code, 302)
        assignment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(assignment.status, DeliveryAssignment.AssignmentStatus.PICKED_UP)
        self.assertEqual(order.status, Order.Status.OUT_FOR_DELIVERY)

        # 4. Complete Delivery with Correct OTP (Should Succeed)
        res_correct_otp = self.client.post(
            reverse('delivery:complete_delivery', kwargs={'assignment_id': assignment.id}),
            {'delivery_otp': assignment.delivery_otp}
        )
        self.assertEqual(res_correct_otp.status_code, 302)
        assignment.refresh_from_db()
        order.refresh_from_db()
        payment.refresh_from_db()
        self.rider_profile.refresh_from_db()

        self.assertEqual(assignment.status, DeliveryAssignment.AssignmentStatus.DELIVERED)
        self.assertEqual(order.status, Order.Status.DELIVERED)
        self.assertEqual(payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.rider_profile.total_deliveries, 1)
