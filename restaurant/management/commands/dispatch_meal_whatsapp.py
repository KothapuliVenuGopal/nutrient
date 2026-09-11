import sys
from django.core.management.base import BaseCommand
from django.utils import timezone
from restaurant.whatsapp_service import dispatch_meal_broadcast
from restaurant.models import WhatsAppTemplate


class Command(BaseCommand):
    help = "Dispatches scheduled daily meal WhatsApp notifications (Breakfast, Lunch, Snack, Dinner) with customer personalization."

    def add_arguments(self, parser):
        parser.add_argument(
            '--meal',
            type=str,
            choices=['BREAKFAST', 'LUNCH', 'SNACK', 'DINNER', 'breakfast', 'lunch', 'snack', 'dinner'],
            help='Designated meal session to broadcast. If omitted, automatically determined from current time.'
        )
        parser.add_argument(
            '--audience',
            type=str,
            default='ALL',
            choices=['ALL', 'SUBSCRIBERS', 'NON_SUBSCRIBERS', 'VEG', 'NON_VEG'],
            help='Target customer segment (ALL, SUBSCRIBERS, NON_SUBSCRIBERS, VEG, NON_VEG).'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate broadcast and print preview messages without saving logs.'
        )

    def determine_current_meal_slot(self):
        now = timezone.localtime()
        minutes = now.hour * 60 + now.minute

        if 420 <= minutes < 690:       # 07:00 AM - 11:30 AM
            return 'BREAKFAST'
        elif 690 <= minutes < 960:     # 11:30 AM - 04:00 PM
            return 'LUNCH'
        elif 960 <= minutes < 1140:    # 04:00 PM - 07:00 PM
            return 'SNACK'
        elif 1140 <= minutes < 1380:   # 07:00 PM - 11:00 PM
            return 'DINNER'
        else:
            return 'LUNCH'  # Default daytime fallback

    def handle(self, *args, **options):
        meal_slot = options.get('meal')
        audience = options.get('audience', 'ALL').upper()
        dry_run = options.get('dry_run', False)

        if not meal_slot:
            meal_slot = self.determine_current_meal_slot()
            self.stdout.write(self.style.NOTICE(f"Auto-detected current meal slot: {meal_slot}"))
        else:
            meal_slot = meal_slot.upper()

        self.stdout.write(self.style.SUCCESS(
            f"\n🚀 Starting Daily WhatsApp Meal Broadcast: [{meal_slot}] (Audience: {audience}) {'[DRY RUN]' if dry_run else ''}"
        ))

        res = dispatch_meal_broadcast(meal_slot=meal_slot, audience=audience, dry_run=dry_run)

        if res.get('status') == 'paused':
            self.stdout.write(self.style.WARNING(f"⚠️ {res['message']}"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"✓ Broadcast Execution Completed for {meal_slot}:\n"
            f"  • Total Eligible Recipients: {res['total_eligible']}\n"
            f"  • Successfully Dispatched:   {res['dispatched_count']}\n"
            f"  • Skipped (Already Notified):{res['skipped_count']}\n"
        ))
