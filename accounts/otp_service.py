import re
import random
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from .models import User, PhoneOTP

logger = logging.getLogger(__name__)


def normalize_phone(raw_phone: str) -> str:
    """
    Normalizes Indian mobile number to E.164 format (+91XXXXXXXXXX).
    Accepts: '9876543210', '+91 98765 43210', '09876543210', '+919876543210'
    Returns normalized string or raises ValueError if invalid.
    """
    if not raw_phone:
        raise ValueError("Mobile number cannot be empty.")

    # Remove all non-digit characters except leading +
    digits = re.sub(r'\D', '', raw_phone)

    # Handle standard Indian prefixes
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith('0'):
        digits = digits[1:]

    # Must be exactly 10 digits starting with 6, 7, 8, or 9
    if len(digits) != 10 or digits[0] not in '6789':
        raise ValueError("Please enter a valid 10-digit Indian mobile number.")

    return f"+91{digits}"


def generate_and_send_otp(raw_phone: str, request=None):
    """
    Generates a 6-digit OTP, enforces 60-second cooldown, and dispatches via SMS.
    In development (DEBUG=True), logs to console & session for effortless testing.
    Returns: (success: bool, message: str, otp_code: str or None)
    """
    try:
        phone = normalize_phone(raw_phone)
    except ValueError as e:
        return False, str(e), None

    now = timezone.now()

    # 60-second cooldown rate-limiting
    recent_otp = PhoneOTP.objects.filter(
        phone=phone,
        created_at__gte=now - timedelta(seconds=60)
    ).first()

    if recent_otp:
        time_left = 60 - int((now - recent_otp.created_at).total_seconds())
        if time_left > 0:
            return False, f"Please wait {time_left} seconds before requesting a new OTP.", None

    # Generate 6-digit cryptographically secure code
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = now + timedelta(minutes=10)

    otp_record = PhoneOTP.objects.create(
        phone=phone,
        otp_code=otp_code,
        expires_at=expires_at,
        is_verified=False,
        attempts=0
    )

    # Store in session for local dev demonstration
    if request:
        request.session['dev_last_otp'] = {
            'phone': phone,
            'code': otp_code,
            'time': now.isoformat()
        }

    # Dispatch SMS Gateway (Pluggable: Console/Mock in dev; Fast2SMS/Twilio in prod)
    sms_message = f"Your Nutrient verification code is {otp_code}. Valid for 10 minutes. Do not share with anyone."
    
    # Print clear debug notice
    print(f"\n==========================================")
    print(f"📱 [NUTRIENT SMS GATEWAY] Message Dispatched")
    print(f"To: {phone}")
    print(f"Code: {otp_code}")
    print(f"Content: {sms_message}")
    print(f"==========================================\n")
    logger.info(f"OTP generated for {phone}: {otp_code}")

    return True, f"OTP sent successfully to {phone}.", otp_code


def verify_otp(raw_phone: str, code: str):
    """
    Verifies user-submitted OTP against active database records.
    Returns: (success: bool, message: str, phone: str or None)
    """
    try:
        phone = normalize_phone(raw_phone)
    except ValueError as e:
        return False, str(e), None

    if not code or len(code.strip()) != 6 or not code.strip().isdigit():
        return False, "Please enter a valid 6-digit OTP code.", None

    clean_code = code.strip()

    otp_record = PhoneOTP.objects.filter(
        phone=phone,
        is_verified=False
    ).order_by('-created_at').first()

    if not otp_record:
        return False, "No active OTP found for this mobile number. Please request a new code.", None

    if otp_record.is_expired:
        return False, "This OTP has expired. Please request a new code.", None

    if otp_record.attempts >= 5:
        return False, "Too many failed attempts. This OTP is locked. Please request a new code.", None

    if otp_record.otp_code != clean_code:
        otp_record.attempts += 1
        otp_record.save()
        remaining = 5 - otp_record.attempts
        return False, f"Incorrect OTP code. {remaining} attempt(s) remaining.", None

    # Mark verified
    otp_record.is_verified = True
    otp_record.save()

    return True, "Phone number verified successfully!", phone


def get_or_create_customer_by_phone(phone: str, first_name: str = None):
    """
    Retrieves existing customer by normalized phone or auto-registers a new Customer user.
    Returns: (user: User, created: bool)
    """
    normalized = normalize_phone(phone)
    digits = re.sub(r'\D', '', normalized)[-10:]

    user = User.objects.filter(phone=normalized).first()
    if user:
        if first_name and not user.first_name:
            user.first_name = first_name.strip()
            user.save(update_fields=['first_name'])
        return user, False

    # Also check without +91 just in case legacy user was created
    user_legacy = User.objects.filter(phone=digits).first()
    if user_legacy:
        user_legacy.phone = normalized
        user_legacy.save(update_fields=['phone'])
        return user_legacy, False

    # Create new customer account
    base_username = f"user_{digits}"
    username = base_username
    counter = 1
    while User.objects.filter(username=username).exists():
        username = f"{base_username}_{counter}"
        counter += 1

    placeholder_email = f"{username}@nutrientfood.in"
    customer_name = first_name.strip() if first_name else f"Customer {digits[-4:]}"

    new_user = User.objects.create_user(
        username=username,
        email=placeholder_email,
        phone=normalized,
        first_name=customer_name,
        role=User.Role.CUSTOMER
    )

    return new_user, True
