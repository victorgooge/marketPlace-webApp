import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker

from app.models import Listing, Profile, Category

try:
    from app.models import Follow
    HAS_FOLLOW = True
except ImportError:
    HAS_FOLLOW = False

try:
    from app.models import SavedListing
    HAS_SAVED = True
except ImportError:
    HAS_SAVED = False

try:
    from app.models import Conversation, ChatMessage
    HAS_MESSAGING = True
except ImportError:
    HAS_MESSAGING = False

try:
    from app.models import Review
    HAS_REVIEWS = True
except ImportError:
    HAS_REVIEWS = False

try:
    from app.models import Offer
    HAS_OFFERS = True
except ImportError:
    HAS_OFFERS = False

try:
    from app.models import ListingView
    HAS_VIEWS = True
except ImportError:
    HAS_VIEWS = False


User = get_user_model()
fake = Faker()

CATEGORIES = [
    "Electronics", "Furniture", "Clothing", "Books", "Vehicles",
    "Sports", "Tools", "Musical Instruments", "Collectibles", "Home & Garden",
]

CONDITIONS = ["New", "Like New", "Good", "Fair", "For Parts"]

LISTING_TEMPLATES = {
    "Electronics":         ["MacBook Pro", "iPhone", "iPad", "Sony Headphones", "Samsung Monitor",
                            "Mechanical Keyboard", "Gaming Mouse", "Webcam", "Smart Watch", "Portable Speaker"],
    "Furniture":           ["Ikea Desk", "Office Chair", "Couch", "Bookshelf", "Coffee Table",
                            "Dining Table", "Dresser", "Bed Frame", "Standing Desk", "Filing Cabinet"],
    "Clothing":            ["North Face Jacket", "Nike Shoes", "Levi Jeans", "Patagonia Fleece",
                            "Adidas Hoodie", "Boots", "Vintage Tee", "Rain Jacket", "Sneakers", "Backpack"],
    "Books":               ["Clean Code", "Dune", "The Great Gatsby", "Python Crash Course",
                            "Atomic Habits", "Design Patterns", "LOTR Boxed Set", "DDIA", "1984", "Sapiens"],
    "Vehicles":            ["2015 Honda Civic", "Trek Bike", "Yamaha Scooter", "Ford F-150",
                            "Road Bike", "Mountain Bike", "Electric Scooter", "Kayak", "Surfboard", "Canoe"],
    "Sports":              ["Dumbbells Set", "Yoga Mat", "Resistance Bands", "Pull-up Bar",
                            "Tennis Racket", "Basketball", "Soccer Ball", "Golf Clubs", "Skateboard", "Helmet"],
    "Tools":               ["DeWalt Drill", "Circular Saw", "Toolbox", "Level", "Ladder",
                            "Socket Set", "Air Compressor", "Jigsaw", "Belt Sander", "Heat Gun"],
    "Musical Instruments": ["Fender Stratocaster", "Yamaha Keyboard", "Pearl Drum Kit",
                            "Acoustic Guitar", "Bass Guitar", "Trumpet", "Violin", "Ukulele", "Cajon", "Flute"],
    "Collectibles":        ["Vintage Comic", "Baseball Cards", "Vinyl Record", "Funko Pop",
                            "Pokemon Cards", "LEGO Set", "Stamp Collection", "Coin Collection", "Action Figure", "Poster"],
    "Home & Garden":       ["KitchenAid Mixer", "Instant Pot", "Dyson Vacuum", "Air Purifier",
                            "Lawn Mower", "Pressure Washer", "Blender", "Coffee Maker", "Fire Pit", "Patio Set"],
}

REVIEW_BODIES = [
    "Great seller, super fast and item was exactly as described.",
    "Really smooth transaction. Would definitely buy from again.",
    "Item was in better condition than expected. Very happy.",
    "Communication was excellent and pickup was easy.",
    "Took a little longer than expected but overall a good experience.",
    "Exactly what I was looking for. Fair price and honest description.",
    "Item had a minor flaw not mentioned but overall still good.",
    "Packaged carefully and delivered on time. Highly recommend.",
    "Fast response to questions. Very professional.",
    "Solid transaction. Item is working perfectly.",
]

CONVERSATION_STARTERS = [
    "Hey, is this still available?",
    "Hi! Would you take ${price} for this?",
    "Can you do local pickup?",
    "Does this come with the original box/accessories?",
    "What's the lowest you'd go on price?",
    "Is there any room to negotiate?",
    "When can I come pick this up?",
    "Does it have any damage I should know about?",
]

SELLER_REPLIES = [
    "Yes still available! When works for you?",
    "I could do ${price}, that's my best price.",
    "Yes, pickup works great. I'm in {location}.",
    "Yep, has everything original.",
    "That's a bit low, but I could meet in the middle.",
    "I'm pretty firm on the price honestly.",
    "I'm free this weekend if that works.",
    "Just minor wear, nothing major.",
]

FOLLOW_UP_MESSAGES = [
    "Sounds good! I'll message you when I'm on the way.",
    "Perfect, I'll Venmo you when I arrive.",
    "Great, see you Saturday around noon!",
    "Works for me. Address?",
    "Okay deal! I can come by tomorrow.",
    "Cool, does 2pm work for you?",
    "Awesome, looking forward to it.",
]

# Category slug map for get_or_create
CATEGORY_SLUGS = {
    "Electronics":         "electronics",
    "Furniture":           "furniture",
    "Clothing":            "clothing",
    "Books":               "books",
    "Vehicles":            "vehicles",
    "Sports":              "sports",
    "Tools":               "tools",
    "Musical Instruments": "musical-instruments",
    "Collectibles":        "collectibles",
    "Home & Garden":       "home-garden",
}


class Command(BaseCommand):
    help = "Seed the database with fake marketplace data."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=15,
                            help="Number of fake users to create (default: 15)")
        parser.add_argument("--clear", action="store_true",
                            help="Delete all non-superuser data before seeding")

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write(self.style.WARNING("Clearing existing non-superuser data..."))
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write("  Done.\n")

        num_users = options["users"]
        self.stdout.write(f"Seeding {num_users} users...\n")

        # Ensure Category rows exist
        self._ensure_categories()

        users = self._create_users(num_users)
        self.stdout.write(self.style.SUCCESS(f"  OK {len(users)} users created"))

        listings = self._create_listings(users)
        self.stdout.write(self.style.SUCCESS(f"  OK {len(listings)} listings created"))

        if HAS_FOLLOW:
            self._create_follows(users)
            self.stdout.write(self.style.SUCCESS("  OK Follow relationships created"))

        if HAS_SAVED:
            self._create_saved_listings(users, listings)
            self.stdout.write(self.style.SUCCESS("  OK Saved listings created"))

        if HAS_VIEWS:
            self._create_listing_views(users, listings)
            self.stdout.write(self.style.SUCCESS("  OK Listing view history created"))

        conversations = []
        if HAS_MESSAGING:
            conversations = self._create_conversations(users, listings)
            self.stdout.write(self.style.SUCCESS(f"  OK {len(conversations)} conversations created"))

        if HAS_REVIEWS:
            self._create_reviews(users, conversations)
            self.stdout.write(self.style.SUCCESS("  OK Reviews created"))

        if HAS_OFFERS:
            self._create_offers(users, listings)
            self.stdout.write(self.style.SUCCESS("  OK Offers created"))

        self.stdout.write(self.style.SUCCESS("\nDatabase seeded successfully!"))
        self.stdout.write("Login with any of these accounts (password: password123):")
        for user in users[:5]:
            self.stdout.write(f"  email: {user.email} | username: {user.username}")

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _ensure_categories(self):
        for name in CATEGORIES:
            Category.objects.get_or_create(
                slug=CATEGORY_SLUGS[name],
                defaults={"name": name},
            )

    def _create_users(self, count):
        users = []
        for _ in range(count):
            first = fake.first_name()
            last  = fake.last_name()
            base  = f"{first.lower()}{last.lower()}"
            username = f"{base}{random.randint(1, 999)}"
            email    = f"{username}@{fake.free_email_domain()}"

            while User.objects.filter(email=email).exists():
                email = f"{base}{random.randint(1000, 9999)}@{fake.free_email_domain()}"

            # Ensure username is unique too
            while User.objects.filter(username=username).exists():
                username = f"{base}{random.randint(1, 9999)}"

            user = User.objects.create_user(
                username=username,
                email=email,
                password="password123",
                first_name=first,
                last_name=last,
            )

            self._verify_user(user)
            self._populate_profile(user)
            users.append(user)

        return users

    def _verify_user(self, user):
        """Make the user fully login-capable — no email verification wall, no MFA."""
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])

        # allauth: create a verified EmailAddress record if allauth is installed
        try:
            from allauth.account.models import EmailAddress
            obj, created = EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"primary": True, "verified": True},
            )
            if not obj.verified:
                obj.verified = True
                obj.primary  = True
                obj.save(update_fields=["verified", "primary"])
        except ImportError:
            pass

    def _populate_profile(self, user):
        """Fill in profile fields. Profile is auto-created by signal."""
        try:
            try:
                profile = user.profile
            except Exception:
                profile = Profile(user=user)

            # Profile uses 'about' (not 'bio') and 'location'
            if hasattr(profile, "about"):
                profile.about = fake.paragraph(nb_sentences=2)
            if hasattr(profile, "location"):
                profile.location = f"{fake.city()}, {fake.state_abbr()}"

            profile.save()
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f"    Could not populate profile for {user.username}: {e}"
            ))

    def _create_listings(self, users):
        listings = []
        cat_objects = {c.name: c for c in Category.objects.all()}

        for user in users:
            num = random.randint(4, 10)
            for _ in range(num):
                category_name = random.choice(CATEGORIES)
                condition     = random.choice(CONDITIONS)
                title         = random.choice(LISTING_TEMPLATES[category_name])

                price = round(random.choice([
                    random.uniform(5,    50),
                    random.uniform(50,   300),
                    random.uniform(300,  2000),
                    random.uniform(2000, 8000),
                ]), 2)

                days_ago   = random.randint(0, 180)
                created_at = timezone.now() - timedelta(days=days_ago)

                location = ""
                try:
                    location = user.profile.location or ""
                except Exception:
                    location = fake.city()

                listing = Listing(
                    owner=user,
                    title=f"{condition} {title}",
                    caption=fake.paragraph(nb_sentences=random.randint(2, 5)),
                    price=price,
                    is_active=random.random() > 0.15,
                    category=cat_objects.get(category_name),
                )
                listing.save()

                # Backdate timestamp via update() to bypass auto_now_add / default
                Listing.objects.filter(pk=listing.pk).update(timestamp=created_at)
                listing.refresh_from_db()

                listings.append(listing)

        return listings

    def _create_follows(self, users):
        created = set()
        for user in users:
            others  = [u for u in users if u != user]
            targets = random.sample(others, k=min(random.randint(3, 8), len(others)))
            for target in targets:
                pair = (user.pk, target.pk)
                if pair not in created:
                    Follow.objects.get_or_create(follower=user, following=target)
                    created.add(pair)

    def _create_saved_listings(self, users, listings):
        for user in users:
            others  = [l for l in listings if l.owner != user]
            to_save = random.sample(others, k=min(random.randint(3, 8), len(others)))
            for listing in to_save:
                SavedListing.objects.get_or_create(user=user, listing=listing)

    def _create_listing_views(self, users, listings):
        """Each user has 2–3 preferred categories they browse heavily."""
        cat_field_map = {c.name: c for c in Category.objects.all()}

        for user in users:
            preferred_cats = random.sample(CATEGORIES, k=random.randint(2, 3))
            preferred_cat_objs = [cat_field_map[c] for c in preferred_cats if c in cat_field_map]

            preferred = [l for l in listings if l.category in preferred_cat_objs and l.owner != user]
            other     = [l for l in listings if l.category not in preferred_cat_objs and l.owner != user]

            to_view = (
                random.sample(preferred, k=min(random.randint(8, 20), len(preferred))) +
                random.sample(other,     k=min(random.randint(2, 8),  len(other)))
            )
            for listing in to_view:
                lv, created = ListingView.objects.get_or_create(
                    listing=listing,
                    viewer=user,
                )
                if created:
                    # Backdate viewed_at (auto_now_add) via update()
                    ListingView.objects.filter(pk=lv.pk).update(
                        viewed_at=timezone.now() - timedelta(days=random.randint(0, 60))
                    )

    def _create_conversations(self, users, listings):
        conversations = []
        pairs_used    = set()
        target_count  = random.randint(30, 50)
        attempts      = 0

        while len(conversations) < target_count and attempts < 500:
            attempts += 1
            buyer   = random.choice(users)
            listing = random.choice([l for l in listings if l.owner != buyer])
            seller  = listing.owner
            pair    = tuple(sorted([buyer.pk, seller.pk]))

            if pair in pairs_used:
                continue
            pairs_used.add(pair)

            convo = Conversation.objects.create(listing=listing)
            convo.participants.add(buyer, seller)

            num_messages = random.randint(3, 12)
            self._create_message_thread(convo, buyer, seller, listing, num_messages)
            conversations.append(convo)

        return conversations

    def _create_message_thread(self, convo, buyer, seller, listing, num_messages):
        price_offer = round(float(listing.price) * random.uniform(0.7, 0.95))
        location    = getattr(getattr(seller, "profile", None), "location", "my place") or "my place"

        thread = [(buyer, random.choice(CONVERSATION_STARTERS))]

        pool     = SELLER_REPLIES + FOLLOW_UP_MESSAGES
        speakers = [seller, buyer] * ((num_messages // 2) + 1)
        for speaker in speakers[: num_messages - 1]:
            thread.append((speaker, random.choice(pool)))

        base_time = timezone.now() - timedelta(days=random.randint(0, 90))
        for i, (sender, body) in enumerate(thread):
            body = body.replace("${price}", f"${price_offer}").replace("{location}", location)
            sent_at = base_time + timedelta(minutes=i * random.randint(2, 120))

            msg = ChatMessage(
                conversation=convo,
                sender=sender,
                body=body,
                read=(i < len(thread) - 1),  # last message is unread
            )
            msg.save()
            # Backdate sent_at (auto_now_add) via update()
            ChatMessage.objects.filter(pk=msg.pk).update(sent_at=sent_at)

    def _create_reviews(self, users, conversations):
        reviewed_pairs = set()
        for convo in conversations:
            participants = list(convo.participants.all())
            if len(participants) < 2:
                continue

            reviewer, seller = participants[0], participants[1]
            pair = (reviewer.pk, seller.pk)

            if random.random() > 0.6 or pair in reviewed_pairs or reviewer == seller:
                continue
            reviewed_pairs.add(pair)

            Review.objects.create(
                reviewer=reviewer,
                seller=seller,
                rating=random.choices([3, 4, 5], weights=[1, 3, 6])[0],
                body=random.choice(REVIEW_BODIES),
            )

    def _create_offers(self, users, listings):
        sample = random.sample(listings, k=min(20, len(listings)))
        for listing in sample:
            buyer       = random.choice([u for u in users if u != listing.owner])
            offer_price = round(float(listing.price) * random.uniform(0.6, 0.9), 2)

            Offer.objects.get_or_create(
                listing=listing,
                buyer=buyer,
                defaults={
                    "amount":  offer_price,
                    "message": f"Would you take ${offer_price}? I can pick up this week.",
                    "status":  random.choice(["pending", "accepted", "declined"]),
                },
            )
