import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User, Address
from restaurant.models import RestaurantProfile, BusinessHour
from menu.models import Category, FoodItem, CustomizationGroup, CustomizationOption
from orders.models import Coupon
from delivery.models import DeliveryPartnerProfile
from reviews.models import Review
from subscriptions.models import SubscriptionPlan, CustomerSubscription, DailySubscriptionDelivery


class Command(BaseCommand):
    help = "Seed initial production-grade data for NUTRIENT / THE SUPER FOOD KITCHEN"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🌱 Seeding NUTRIENT / THE SUPER FOOD KITCHEN Data..."))

        # 1. Restaurant Profile & Operating Hours
        profile = RestaurantProfile.get_instance()
        profile.name = "NUTRIENT / THE SUPER FOOD KITCHEN"
        profile.tagline = "Whole Nutritious Food for Balanced Energy, Strong Immunity & Vitality"
        profile.secondary_tagline = "Quick Free Home Delivery within 3km • Weekly & Monthly Subscriptions"
        profile.description = (
            "Whole foods are minimally processed and full of vitamins, minerals, fiber and antioxidants. "
            "By focusing on natural, nutrient-dense options, you can enjoy the benefits of balanced energy, "
            "strong immunity and overall vitality. Rich in vitamins, minerals and fiber, fruits and vegetables "
            "keep your body energized and your immune system strong. Brightly coloured portions like berries, "
            "spinach, carrots and tomatoes are especially packed with antioxidants. Freshly prepared salads, "
            "soups, nutrient snacks, and customizable weekly/monthly meal bowl subscriptions."
        )
        profile.phone = "+91 7993476624"
        profile.whatsapp_number = "+91 7993476624"
        profile.email = "orders@nutrientfood.in"
        profile.address_line = "Plot 42, Silicon Valley Lane, Madhapur, HITEC City"
        profile.city = "Hyderabad"
        profile.state = "Telangana"
        profile.pincode = "500081"
        profile.min_order_value = Decimal("119.00")
        profile.default_delivery_charge = Decimal("30.00")
        profile.free_delivery_threshold = Decimal("300.00")
        profile.tax_percentage = Decimal("5.00")
        profile.delivery_radius_km = Decimal("3.0")
        profile.avg_preparation_time_mins = 20
        profile.is_accepting_orders = True
        profile.save()
        self.stdout.write(self.style.SUCCESS(f"✓ Restaurant Profile configured: {profile.name}"))

        # Weekly Hours (Mon - Sun, 09:00 to 23:00)
        for day in BusinessHour.DayOfWeek.values:
            BusinessHour.objects.get_or_create(
                restaurant=profile,
                day_of_week=day,
                defaults={
                    'opening_time': datetime.time(9, 0),
                    'closing_time': datetime.time(23, 0),
                    'is_closed': False
                }
            )
        self.stdout.write(self.style.SUCCESS("✓ Business operating hours (09:00 AM - 11:00 PM) verified"))

        # 2. Users (Admin, Riders, Customers)
        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                'email': "admin@nutrientfood.in",
                'first_name': "Executive",
                'last_name': "Chef",
                'role': User.Role.RESTAURANT_ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'phone': "+91 7993476624"
            }
        )
        admin_user.set_password("Nutrient@2026")
        admin_user.role = User.Role.RESTAURANT_ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        # Delivery Partner 1 (Bike)
        rider1, _ = User.objects.get_or_create(
            username="rider_rajesh",
            defaults={
                'email': "rajesh@nutrientfood.in",
                'first_name': "Rajesh",
                'last_name': "Kumar",
                'role': User.Role.DELIVERY_PARTNER,
                'phone': "+91 9876543201"
            }
        )
        rider1.set_password("Nutrient@2026")
        rider1.role = User.Role.DELIVERY_PARTNER
        rider1.save()
        DeliveryPartnerProfile.objects.update_or_create(
            user=rider1,
            defaults={
                'vehicle_type': DeliveryPartnerProfile.VehicleType.MOTORCYCLE,
                'vehicle_number': "TS 09 EA 4521",
                'is_available': True,
                'rating': Decimal("4.95"),
                'total_deliveries': 142
            }
        )

        # Delivery Partner 2 (EV Scooter)
        rider2, _ = User.objects.get_or_create(
            username="rider_vikram",
            defaults={
                'email': "vikram@nutrientfood.in",
                'first_name': "Vikram",
                'last_name': "Reddy",
                'role': User.Role.DELIVERY_PARTNER,
                'phone': "+91 9876543202"
            }
        )
        rider2.set_password("Nutrient@2026")
        rider2.role = User.Role.DELIVERY_PARTNER
        rider2.save()
        DeliveryPartnerProfile.objects.update_or_create(
            user=rider2,
            defaults={
                'vehicle_type': DeliveryPartnerProfile.VehicleType.SCOOTER,
                'vehicle_number': "TS 09 EV 9901",
                'is_available': True,
                'rating': Decimal("5.00"),
                'total_deliveries': 89
            }
        )

        # Customer 1
        cust1, _ = User.objects.get_or_create(
            username="ananya_sharma",
            defaults={
                'email': "ananya@example.com",
                'first_name': "Ananya",
                'last_name': "Sharma",
                'role': User.Role.CUSTOMER,
                'phone': "+91 9848022338"
            }
        )
        cust1.set_password("Nutrient@2026")
        cust1.role = User.Role.CUSTOMER
        cust1.save()
        addr1, _ = Address.objects.get_or_create(
            user=cust1,
            address_type=Address.AddressType.HOME,
            defaults={
                'contact_name': "Ananya Sharma",
                'contact_phone': "+91 9848022338",
                'apartment_flat': "Flat 502, Tower B, Prestige Sky",
                'street_address': "Inorbit Mall Road, Madhapur",
                'landmark': "Near Cyber Towers (Within 3km)",
                'city': "Hyderabad",
                'state': "Telangana",
                'pincode': "500081",
                'is_default': True
            }
        )

        # Customer 2
        cust2, _ = User.objects.get_or_create(
            username="rohit_verma",
            defaults={
                'email': "rohit@example.com",
                'first_name': "Rohit",
                'last_name': "Verma",
                'role': User.Role.CUSTOMER,
                'phone': "+91 9988771122"
            }
        )
        cust2.set_password("Nutrient@2026")
        cust2.role = User.Role.CUSTOMER
        cust2.save()
        Address.objects.get_or_create(
            user=cust2,
            address_type=Address.AddressType.WORK,
            defaults={
                'contact_name': "Rohit Verma",
                'contact_phone': "+91 9988771122",
                'apartment_flat': "Level 6, Tech Hub 3",
                'street_address': "Hitec City Main Road",
                'landmark': "Opposite Mindspace West Gate (Within 3km)",
                'city': "Hyderabad",
                'state': "Telangana",
                'pincode': "500081",
                'is_default': True
            }
        )
        self.stdout.write(self.style.SUCCESS("✓ Seeded Admin, 2 Riders, and 2 Customers with addresses"))

        # 3. Menu Categories
        categories_data = [
            ("Signature Protein Bowls", "signature-protein-bowls", "Customizable high-protein nutrition bowls served with dressing & super drink.", 1),
            ("Signature Meal Bowls", "signature-meal-bowls", "Wholesome grain & curry bowls served with vegetable raita & super drink.", 2),
            ("Snack Bowls", "snack-bowls", "Freshly prepared nutrient snacks, salads, roasted nuts and guilt-free seeds.", 3),
            ("Nourishing Soups", "nourishing-soups", "Warm, mineral-rich cleansing broths served with crispy croutons.", 4),
        ]
        cat_map = {}
        for name, slug, desc, order in categories_data:
            cat, _ = Category.objects.update_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc, 'display_order': order, 'is_active': True}
            )
            cat_map[slug] = cat
        self.stdout.write(self.style.SUCCESS("✓ Menu categories created"))

        # Purge any food items that are not part of the official 15 items
        official_slugs = [
            "veg-protein-bowl",
            "non-veg-protein-bowl",
            "veg-meal-bowl",
            "non-veg-meal-bowl",
            "fruit-salad-bowl",
            "boiled-egg-and-veg",
            "boiled-peanut-salad",
            "boiled-channa-salad",
            "sprout-salad-bowl",
            "roasted-peanuts",
            "roasted-sweet-potato",
            "roasted-makhana",
            "roasted-mix-nuts",
            "vegetable-soup-and-crotons",
            "non-veg-soup-and-crotons",
        ]
        deleted_count, _ = FoodItem.objects.exclude(slug__in=official_slugs).delete()
        if deleted_count > 0:
            self.stdout.write(self.style.WARNING(f"✓ Purged {deleted_count} non-menu items not in official menu"))

        # 4. The 4 Signature Customizable Bowls (with 30% Discount Display)
        # 1) Veg Protein Bowl (@ ₹179, MRP ₹259)
        v_pb, _ = FoodItem.objects.update_or_create(
            slug="veg-protein-bowl",
            defaults={
                'category': cat_map['signature-protein-bowls'],
                'name': "Veg Protein Bowl",
                'description': "Vegetable protein bowl + house dressing + complimentary super drink. Loaded with fresh paneer, soya bean, sprouts, rajma, avocado, broccoli, and seasonal greens.",
                'food_type': FoodItem.FoodType.VEG,
                'price': Decimal("259.00"),            # Actual MRP
                'discounted_price': Decimal("179.00"), # 70% Discounted Price (30% OFF)
                'calories': 390,
                'protein_grams': Decimal("28.0"),
                'carbs_grams': Decimal("34.0"),
                'fats_grams': Decimal("11.0"),
                'fiber_grams': Decimal("9.0"),
                'is_high_protein': True,
                'is_bestseller': True,
                'is_available': True,
                'available_slots': ['BREAKFAST', 'LUNCH', 'DINNER', 'ALL_DAY'],
                'auto_timing_enabled': True,
                'preparation_time_mins': 15,
            }
        )

        # Customization Groups for Veg Protein Bowl
        CustomizationGroup.objects.filter(food_item=v_pb).delete()
        g_prot = CustomizationGroup.objects.create(
            food_item=v_pb, name="Choose Protein Source", min_choices=1, max_choices=2, is_required=True, display_order=1
        )
        for opt in ["Fresh Paneer", "Soya Bean", "Sprouts", "Rajma", "Roasted Peanuts", "Kabuli Channa"]:
            CustomizationOption.objects.create(group=g_prot, name=opt, protein_modifier=Decimal("12.0"))

        g_veg = CustomizationGroup.objects.create(
            food_item=v_pb, name="Choose Veggies & Greens (Pick up to 4)", min_choices=1, max_choices=4, is_required=True, display_order=2
        )
        for opt in ["Avocado", "Capsicum", "Cucumber", "Tomato", "Green Beans", "Carrots", "Spinach", "Beetroot", "Green Peas", "Lentil", "Sweet Potato", "Cauliflower", "Onion", "Broccoli", "Lettuce"]:
            CustomizationOption.objects.create(group=g_veg, name=opt)

        g_dress = CustomizationGroup.objects.create(
            food_item=v_pb, name="Choose House Dressing", min_choices=1, max_choices=1, is_required=True, display_order=3
        )
        for opt in ["Zesty Herb Dressing", "Lemon Olive Oil Vinaigrette", "Fresh Mint Yogurt Dip", "Tahini Garlic Drizzle"]:
            CustomizationOption.objects.create(group=g_dress, name=opt)

        g_drink = CustomizationGroup.objects.create(
            food_item=v_pb, name="Choose Included Super Drink", min_choices=1, max_choices=1, is_required=True, display_order=4
        )
        for opt in ["Cold-Pressed ABC Detox Elixir", "Chia Lemon Hydration Water", "Herbal Mint Cooler", "Organic Green Tea"]:
            CustomizationOption.objects.create(group=g_drink, name=opt)

        # 2) Non-Veg Protein Bowl (@ ₹219, MRP ₹319)
        nv_pb, _ = FoodItem.objects.update_or_create(
            slug="non-veg-protein-bowl",
            defaults={
                'category': cat_map['signature-protein-bowls'],
                'name': "Non-Veg Protein Bowl",
                'description': "Non-veg protein bowl + house dressing + complimentary super drink. Packed with tender grilled chicken, oven roast chicken, boiled eggs, sweet corn, and farm-fresh veggies.",
                'food_type': FoodItem.FoodType.NON_VEG,
                'price': Decimal("319.00"),            # Actual MRP
                'discounted_price': Decimal("219.00"), # 70% Discounted Price (30% OFF)
                'calories': 460,
                'protein_grams': Decimal("42.0"),
                'carbs_grams': Decimal("26.0"),
                'fats_grams': Decimal("13.0"),
                'fiber_grams': Decimal("7.0"),
                'is_high_protein': True,
                'is_bestseller': True,
                'is_available': True,
                'available_slots': ['BREAKFAST', 'LUNCH', 'DINNER', 'ALL_DAY'],
                'auto_timing_enabled': True,
                'preparation_time_mins': 15,
            }
        )
        CustomizationGroup.objects.filter(food_item=nv_pb).delete()
        g_nv_prot = CustomizationGroup.objects.create(
            food_item=nv_pb, name="Choose Protein Source", min_choices=1, max_choices=2, is_required=True, display_order=1
        )
        for opt in ["Tender Grilled Chicken", "Herb Oven Roast Chicken", "Hard Boiled Eggs (2 pcs)"]:
            CustomizationOption.objects.create(group=g_nv_prot, name=opt, protein_modifier=Decimal("20.0"))

        g_nv_veg = CustomizationGroup.objects.create(
            food_item=nv_pb, name="Choose Veggies & Greens (Pick up to 4)", min_choices=1, max_choices=4, is_required=True, display_order=2
        )
        for opt in ["Green Beans", "Green Peas", "Carrots", "Broccoli", "Sweet Corn", "Capsicum", "Baby Spinach", "Roasted Sweet Potato", "Tomato", "Onion", "Crisp Lettuce"]:
            CustomizationOption.objects.create(group=g_nv_veg, name=opt)

        g_nv_dress = CustomizationGroup.objects.create(
            food_item=nv_pb, name="Choose House Dressing", min_choices=1, max_choices=1, is_required=True, display_order=3
        )
        for opt in ["Zesty Herb Dressing", "Lemon Olive Oil Vinaigrette", "Smoked Chipotle Yogurt Dip", "Honey Dijon Mustard"]:
            CustomizationOption.objects.create(group=g_nv_dress, name=opt)

        g_nv_drink = CustomizationGroup.objects.create(
            food_item=nv_pb, name="Choose Included Super Drink", min_choices=1, max_choices=1, is_required=True, display_order=4
        )
        for opt in ["Cold-Pressed ABC Detox Elixir", "Chia Lemon Hydration Water", "Herbal Mint Cooler", "Organic Green Tea"]:
            CustomizationOption.objects.create(group=g_nv_drink, name=opt)

        # 3) Veg Meal Bowl (@ ₹229, MRP ₹329)
        v_mb, _ = FoodItem.objects.update_or_create(
            slug="veg-meal-bowl",
            defaults={
                'category': cat_map['signature-meal-bowls'],
                'name': "Veg Meal Bowl",
                'description': "Vegetables meal bowl + refreshing vegetable raita + complimentary super drink. Choose your favorite grains (brown rice, quinoa, chapatti) paired with homestyle protein curries.",
                'food_type': FoodItem.FoodType.VEG,
                'price': Decimal("329.00"),            # Actual MRP
                'discounted_price': Decimal("229.00"), # 70% Discounted Price (30% OFF)
                'calories': 520,
                'protein_grams': Decimal("26.0"),
                'carbs_grams': Decimal("64.0"),
                'fats_grams': Decimal("14.0"),
                'fiber_grams': Decimal("10.0"),
                'is_high_protein': True,
                'is_available': True,
                'available_slots': ['LUNCH', 'DINNER'],
                'auto_timing_enabled': True,
                'preparation_time_mins': 20,
            }
        )
        CustomizationGroup.objects.filter(food_item=v_mb).delete()
        g_vmb_base = CustomizationGroup.objects.create(
            food_item=v_mb, name="Choose Grains / Base", min_choices=1, max_choices=1, is_required=True, display_order=1
        )
        for opt in ["Organic Brown Rice", "Tri-Color Quinoa", "Traditional Red Rice", "Whole Wheat Chapatti (3 pcs)", "Nutrient Vegetable Pulao"]:
            CustomizationOption.objects.create(group=g_vmb_base, name=opt)

        g_vmb_curry = CustomizationGroup.objects.create(
            food_item=v_mb, name="Choose Main Curry / Dish", min_choices=1, max_choices=2, is_required=True, display_order=2
        )
        for opt in ["Palak Paneer", "Channa Masala", "Soya Bean Curry", "Rajma Masala", "Beetroot Fry", "Paneer Masala", "Crispy Veggie Rolls"]:
            CustomizationOption.objects.create(group=g_vmb_curry, name=opt, protein_modifier=Decimal("10.0"))

        g_vmb_veg = CustomizationGroup.objects.create(
            food_item=v_mb, name="Choose Vegetables Style", min_choices=1, max_choices=1, is_required=True, display_order=3
        )
        for opt in ["Sautéed Seasonal Vegetables", "Steamed Garden Vegetables"]:
            CustomizationOption.objects.create(group=g_vmb_veg, name=opt)

        g_vmb_raita = CustomizationGroup.objects.create(
            food_item=v_mb, name="Included Fresh Raita", min_choices=1, max_choices=1, is_required=True, display_order=4
        )
        CustomizationOption.objects.create(group=g_vmb_raita, name="Fresh Vegetable Raita")

        g_vmb_drink = CustomizationGroup.objects.create(
            food_item=v_mb, name="Choose Included Super Drink", min_choices=1, max_choices=1, is_required=True, display_order=5
        )
        for opt in ["Cold-Pressed ABC Detox Elixir", "Chia Lemon Hydration Water", "Herbal Mint Cooler", "Organic Green Tea"]:
            CustomizationOption.objects.create(group=g_vmb_drink, name=opt)

        # 4) Non-Veg Meal Bowl (@ ₹279, MRP ₹399)
        nv_mb, _ = FoodItem.objects.update_or_create(
            slug="non-veg-meal-bowl",
            defaults={
                'category': cat_map['signature-meal-bowls'],
                'name': "Non-Veg Meal Bowl",
                'description': "Non-veg meal bowl + fresh vegetable raita + complimentary super drink. Hearty grains paired with succulent chicken curries, roasted chicken, chicken tacos or egg specialties.",
                'food_type': FoodItem.FoodType.NON_VEG,
                'price': Decimal("399.00"),            # Actual MRP
                'discounted_price': Decimal("279.00"), # 70% Discounted Price (30% OFF)
                'calories': 580,
                'protein_grams': Decimal("44.0"),
                'carbs_grams': Decimal("58.0"),
                'fats_grams': Decimal("16.0"),
                'fiber_grams': Decimal("8.0"),
                'is_high_protein': True,
                'is_bestseller': True,
                'is_available': True,
                'available_slots': ['LUNCH', 'DINNER'],
                'auto_timing_enabled': True,
                'preparation_time_mins': 20,
            }
        )
        CustomizationGroup.objects.filter(food_item=nv_mb).delete()
        g_nvmb_base = CustomizationGroup.objects.create(
            food_item=nv_mb, name="Choose Grains / Base", min_choices=1, max_choices=1, is_required=True, display_order=1
        )
        for opt in ["Organic Brown Rice", "Tri-Color Quinoa", "Traditional Red Rice", "Whole Wheat Chapathi (3 pcs)", "High-Protein Chicken Pulao"]:
            CustomizationOption.objects.create(group=g_nvmb_base, name=opt)

        g_nvmb_curry = CustomizationGroup.objects.create(
            food_item=nv_mb, name="Choose Non-Veg Specialty", min_choices=1, max_choices=2, is_required=True, display_order=2
        )
        for opt in ["Crispy Chicken Fry", "Homestyle Chicken Curry", "Herb Roasted Chicken", "Spiced Egg Masala", "Grilled Chicken Rolls", "High-Protein Chicken Tacos"]:
            CustomizationOption.objects.create(group=g_nvmb_curry, name=opt, protein_modifier=Decimal("20.0"))

        g_nvmb_veg = CustomizationGroup.objects.create(
            food_item=nv_mb, name="Choose Vegetables Style", min_choices=1, max_choices=1, is_required=True, display_order=3
        )
        for opt in ["Sautéed Seasonal Vegetables", "Steamed Garden Vegetables"]:
            CustomizationOption.objects.create(group=g_nvmb_veg, name=opt)

        g_nvmb_raita = CustomizationGroup.objects.create(
            food_item=nv_mb, name="Included Fresh Raita", min_choices=1, max_choices=1, is_required=True, display_order=4
        )
        CustomizationOption.objects.create(group=g_nvmb_raita, name="Fresh Vegetable Raita")

        g_nvmb_drink = CustomizationGroup.objects.create(
            food_item=nv_mb, name="Choose Included Super Drink", min_choices=1, max_choices=1, is_required=True, display_order=5
        )
        for opt in ["Cold-Pressed ABC Detox Elixir", "Chia Lemon Hydration Water", "Herbal Mint Cooler", "Organic Green Tea"]:
            CustomizationOption.objects.create(group=g_nvmb_drink, name=opt)

        self.stdout.write(self.style.SUCCESS("✓ Seeded 4 Signature Bowls with Customization Groups & 30% Off Pricing"))

        # 5. Snack Bowls (@ ₹119, MRP ₹169)
        snacks_data = [
            ("Fruit Salad Bowl", "fruit-salad-bowl", "Seasonal hand-cut antioxidant fruits including berries, melon, kiwi, and pomegranate with mint.", FoodItem.FoodType.VEGAN, 180, Decimal("3.0"), Decimal("42.0"), Decimal("1.0"), Decimal("6.0"), ['BREAKFAST', 'SNACK']),
            ("Boiled Egg and Veg", "boiled-egg-and-veg", "Organic boiled farm eggs served with steamed carrots, broccoli florets, and light pepper dust.", FoodItem.FoodType.NON_VEG, 210, Decimal("16.0"), Decimal("12.0"), Decimal("9.0"), Decimal("4.0"), ['BREAKFAST', 'SNACK', 'DINNER']),
            ("Boiled Peanut Salad", "boiled-peanut-salad", "Slow-steamed protein peanuts tossed with finely diced onions, tomatoes, green chillies, and lemon juice.", FoodItem.FoodType.VEGAN, 240, Decimal("12.0"), Decimal("22.0"), Decimal("14.0"), Decimal("5.0"), ['BREAKFAST', 'SNACK']),
            ("Boiled Channa Salad", "boiled-channa-salad", "Soft boiled chickpeas mixed with crunchy cucumbers, cilantro, chaat herbs, and virgin olive oil.", FoodItem.FoodType.VEGAN, 230, Decimal("11.0"), Decimal("32.0"), Decimal("5.0"), Decimal("8.0"), ['BREAKFAST', 'SNACK']),
            ("Sprout Salad Bowl", "sprout-salad-bowl", "Freshly sprouted green moong and legumes loaded with enzymes, diced tomatoes, and lemon drizzle.", FoodItem.FoodType.VEGAN, 170, Decimal("14.0"), Decimal("24.0"), Decimal("2.0"), Decimal("7.0"), ['BREAKFAST', 'SNACK', 'DINNER']),
            ("Roasted Peanuts", "roasted-peanuts", "Slow dry-roasted peanuts with Himalayan pink salt and cracked black pepper. Zero oil.", FoodItem.FoodType.VEGAN, 260, Decimal("13.0"), Decimal("16.0"), Decimal("18.0"), Decimal("4.0"), ['SNACK']),
            ("Roasted Sweet Potato", "roasted-sweet-potato", "Charred sweet potato cubes lightly tossed with roasted cumin, rock salt, and fresh lime.", FoodItem.FoodType.VEGAN, 190, Decimal("3.0"), Decimal("44.0"), Decimal("1.0"), Decimal("6.0"), ['SNACK']),
            ("Roasted Makhana", "roasted-makhana", "Crunchy popped lotus seeds dry-roasted with turmeric, pepper, and pink salt. Super light snack.", FoodItem.FoodType.VEGAN, 140, Decimal("5.0"), Decimal("28.0"), Decimal("1.0"), Decimal("4.0"), ['SNACK']),
            ("Roasted Mix Nuts", "roasted-mix-nuts", "Premium roasted almonds, walnuts, cashews, and pumpkin seeds rich in omega-3 healthy fats.", FoodItem.FoodType.VEGAN, 290, Decimal("10.0"), Decimal("14.0"), Decimal("24.0"), Decimal("5.0"), ['BREAKFAST', 'SNACK']),
        ]
        for s_name, s_slug, s_desc, s_type, s_cal, s_prot, s_carb, s_fat, s_fib, s_slots in snacks_data:
            FoodItem.objects.update_or_create(
                slug=s_slug,
                defaults={
                    'category': cat_map['snack-bowls'],
                    'name': s_name,
                    'description': s_desc,
                    'food_type': s_type,
                    'price': Decimal("169.00"),            # Actual MRP
                    'discounted_price': Decimal("119.00"), # 70% Discounted Price (30% OFF)
                    'calories': s_cal,
                    'protein_grams': s_prot,
                    'carbs_grams': s_carb,
                    'fats_grams': s_fat,
                    'fiber_grams': s_fib,
                    'is_available': True,
                    'available_slots': s_slots,
                    'auto_timing_enabled': True,
                    'preparation_time_mins': 10,
                }
            )
        self.stdout.write(self.style.SUCCESS("✓ Seeded 9 Snack Bowls (@ ₹119, 30% OFF)"))

        # 6. Nourishing Warm Soups
        soups_data = [
            ("Vegetable Soup and Crotons", "vegetable-soup-and-crotons", "Velvety slow-simmered vegetable broth packed with antioxidants, minerals, and served with oven-crisp herb croutons.", FoodItem.FoodType.VEGAN, Decimal("215.00"), Decimal("149.00"), 160, Decimal("6.0"), Decimal("28.0"), Decimal("4.0"), Decimal("5.0"), ['LUNCH', 'SNACK', 'DINNER']),
            ("Non-Veg Soup and Crotons", "non-veg-soup-and-crotons", "Slow-simmered organic chicken and herb broth infused with ginger, peppercorns, and garlic. Served with crispy croutons.", FoodItem.FoodType.NON_VEG, Decimal("259.00"), Decimal("179.00"), 220, Decimal("24.0"), Decimal("18.0"), Decimal("5.0"), Decimal("3.0"), ['LUNCH', 'SNACK', 'DINNER']),
        ]
        for soup_name, soup_slug, soup_desc, soup_type, soup_mrp, soup_price, soup_cal, soup_prot, soup_carb, soup_fat, soup_fib, soup_slots in soups_data:
            FoodItem.objects.update_or_create(
                slug=soup_slug,
                defaults={
                    'category': cat_map['nourishing-soups'],
                    'name': soup_name,
                    'description': soup_desc,
                    'food_type': soup_type,
                    'price': soup_mrp,
                    'discounted_price': soup_price,
                    'calories': soup_cal,
                    'protein_grams': soup_prot,
                    'carbs_grams': soup_carb,
                    'fats_grams': soup_fat,
                    'fiber_grams': soup_fib,
                    'is_available': True,
                    'available_slots': soup_slots,
                    'auto_timing_enabled': True,
                    'preparation_time_mins': 15,
                }
            )
        self.stdout.write(self.style.SUCCESS("✓ Seeded 2 Nourishing Soups with Crotons (@ ₹149 & ₹179, 30% OFF)"))

        # 7. Subscription Plans (8 Plans: 4 Bowl Types × Weekly/Monthly)
        plans_data = [
            # Veg Protein Bowl Subscription
            ("Veg Protein Bowl Subscription (Weekly)", "veg-protein-bowl-subscription-weekly", SubscriptionPlan.BowlType.VEG_PROTEIN, SubscriptionPlan.Duration.WEEKLY, 7, Decimal("1790.00"), Decimal("1253.00"), 1),
            ("Veg Protein Bowl Subscription (Monthly)", "veg-protein-bowl-subscription-monthly", SubscriptionPlan.BowlType.VEG_PROTEIN, SubscriptionPlan.Duration.MONTHLY, 30, Decimal("7670.00"), Decimal("5370.00"), 2),
            
            # Non-Veg Protein Bowl Subscription
            ("Non-Veg Protein Bowl Subscription (Weekly)", "non-veg-protein-bowl-subscription-weekly", SubscriptionPlan.BowlType.NON_VEG_PROTEIN, SubscriptionPlan.Duration.WEEKLY, 7, Decimal("2190.00"), Decimal("1533.00"), 3),
            ("Non-Veg Protein Bowl Subscription (Monthly)", "non-veg-protein-bowl-subscription-monthly", SubscriptionPlan.BowlType.NON_VEG_PROTEIN, SubscriptionPlan.Duration.MONTHLY, 30, Decimal("9390.00"), Decimal("6570.00"), 4),
            
            # Vegetable Meal Bowl Subscription
            ("Vegetable Meal Bowl Subscription (Weekly)", "vegetable-meal-bowl-subscription-weekly", SubscriptionPlan.BowlType.VEG_MEAL, SubscriptionPlan.Duration.WEEKLY, 7, Decimal("2290.00"), Decimal("1603.00"), 5),
            ("Vegetable Meal Bowl Subscription (Monthly)", "vegetable-meal-bowl-subscription-monthly", SubscriptionPlan.BowlType.VEG_MEAL, SubscriptionPlan.Duration.MONTHLY, 30, Decimal("9810.00"), Decimal("6870.00"), 6),
            
            # Non-Veg Meal Bowl Subscription
            ("Non-Veg Meal Bowl Subscription (Weekly)", "non-veg-meal-bowl-subscription-weekly", SubscriptionPlan.BowlType.NON_VEG_MEAL, SubscriptionPlan.Duration.WEEKLY, 7, Decimal("2790.00"), Decimal("1953.00"), 7),
            ("Non-Veg Meal Bowl Subscription (Monthly)", "non-veg-meal-bowl-subscription-monthly", SubscriptionPlan.BowlType.NON_VEG_MEAL, SubscriptionPlan.Duration.MONTHLY, 30, Decimal("11960.00"), Decimal("8370.00"), 8),
        ]
        plan_objects = {}
        for p_name, p_slug, p_type, p_dur, p_bowls, p_mrp, p_price, p_order in plans_data:
            plan_obj, _ = SubscriptionPlan.objects.update_or_create(
                slug=p_slug,
                defaults={
                    'name': p_name,
                    'bowl_type': p_type,
                    'duration': p_dur,
                    'total_bowls': p_bowls,
                    'original_price': p_mrp,
                    'price': p_price,
                    'discount_percentage': 30,
                    'description': f"Receive 1 fresh, chef-crafted {p_type.replace('_', ' ').title()} + dressing/raita + super drink delivered daily.",
                    'perks': [
                        "Quick Free Home Delivery within 3km radius",
                        "Includes Dressing / Raita & Super Drink daily",
                        "Customize ingredients for each meal in advance",
                        "Pause or reschedule anytime with 1 click",
                        "Guaranteed fresh whole foods, zero preservatives",
                    ],
                    'display_order': p_order,
                    'is_active': True
                }
            )
            plan_objects[p_slug] = plan_obj
        self.stdout.write(self.style.SUCCESS("✓ Seeded 8 Subscription Plans with 30% Off Pricing"))

        # 8. Sample Active Customer Subscription for ananya_sharma
        active_plan = plan_objects['veg-protein-bowl-subscription-weekly']
        today = timezone.localdate()
        sub, _ = CustomerSubscription.objects.update_or_create(
            user=cust1,
            plan=active_plan,
            defaults={
                'status': CustomerSubscription.Status.ACTIVE,
                'start_date': today,
                'end_date': today + datetime.timedelta(days=6),
                'delivery_time_slot': CustomerSubscription.TimeSlot.LUNCH,
                'delivery_address': addr1,
                'bowls_total': 7,
                'bowls_delivered': 2,
                'default_customization': {
                    'selected_options': {
                        'Choose Protein Source': ["Fresh Paneer", "Sprouts"],
                        'Choose Veggies & Greens (Pick up to 4)': ["Avocado", "Broccoli", "Baby Spinach", "Carrots"],
                        'Choose House Dressing': ["Zesty Herb Dressing"],
                        'Choose Included Super Drink': ["Cold-Pressed ABC Detox Elixir"]
                    }
                },
                'special_instructions': "Please call before ringing bell.",
                'payment_status': 'PAID'
            }
        )
        # Schedule daily deliveries
        DailySubscriptionDelivery.objects.filter(subscription=sub).delete()
        for idx in range(7):
            d_date = today + datetime.timedelta(days=idx)
            d_status = DailySubscriptionDelivery.Status.DELIVERED if idx < 2 else DailySubscriptionDelivery.Status.SCHEDULED
            DailySubscriptionDelivery.objects.create(
                subscription=sub,
                delivery_date=d_date,
                time_slot=CustomerSubscription.TimeSlot.LUNCH,
                status=d_status,
                customization=sub.default_customization,
                delivery_otp="4521"
            )
        self.stdout.write(self.style.SUCCESS(f"✓ Seeded active sample subscription for {cust1.username}"))

        # 9. Active promotional coupons
        coupons = [
            ("CLEAN20", "Save 20% on all super food orders above ₹200", Coupon.DiscountType.PERCENTAGE, Decimal("20.00"), Decimal("200.00"), Decimal("80.00")),
            ("HIGHPROTEIN", "Flat ₹50 OFF on high-protein bowls & subscriptions", Coupon.DiscountType.FIXED, Decimal("50.00"), Decimal("300.00"), None),
            ("NUTRIENT10", "10% OFF on any healthy bowl or snack", Coupon.DiscountType.PERCENTAGE, Decimal("10.00"), Decimal("119.00"), Decimal("50.00")),
        ]
        for code, desc, d_type, val, min_amt, max_d in coupons:
            Coupon.objects.update_or_create(
                code=code,
                defaults={
                    'description': desc,
                    'discount_type': d_type,
                    'discount_value': val,
                    'min_order_amount': min_amt,
                    'max_discount_amount': max_d,
                    'valid_from': timezone.now() - datetime.timedelta(days=1),
                    'valid_until': timezone.now() + datetime.timedelta(days=90),
                    'is_active': True,
                    'usage_limit': 1000
                }
            )
        self.stdout.write(self.style.SUCCESS("✓ Active promotional coupons seeded"))

        self.stdout.write(self.style.SUCCESS("\n🎉 NUTRIENT / THE SUPER FOOD KITCHEN database seeded successfully!"))
        self.stdout.write("Default Credentials:")
        self.stdout.write("  Admin:    admin / Nutrient@2026")
        self.stdout.write("  Riders:   rider_rajesh / Nutrient@2026, rider_vikram / Nutrient@2026")
        self.stdout.write("  Customers: ananya_sharma / Nutrient@2026, rohit_verma / Nutrient@2026")
        self.stdout.write("  Coupons:  CLEAN20, HIGHPROTEIN, NUTRIENT10\n")
