from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


class Profile(models.Model):
    user            = models.OneToOneField(User, primary_key=True, verbose_name='user', related_name='profile', on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='pfps', default='pfps/default_pfp.png')
    cover_photo     = models.ImageField(upload_to='covers/', blank=True, null=True)
    location        = models.CharField(max_length=100, blank=True, null=True)
    about           = models.TextField(max_length=500, blank=True, null=True)
    website         = models.URLField(blank=True, null=True)
    is_verified_seller = models.BooleanField(default=False)
    # Computed periodically (e.g. via a signal or scheduled task — not user-editable)
    response_rate      = models.FloatField(default=0.0)
    avg_response_time  = models.DurationField(null=True, blank=True)

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'

    def __str__(self):
        return f"{self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True)  # Font Awesome class e.g. 'fa-laptop'

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Listing(models.Model):
    owner     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    category  = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='listings')
    title     = models.CharField(max_length=255)
    image     = models.ImageField(upload_to='listing_images', blank=True, null=True)
    price     = models.DecimalField(max_digits=10, decimal_places=2)
    caption   = models.TextField()
    timestamp  = models.DateTimeField(default=timezone.now, db_index=True)
    is_active  = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    bumped_at  = models.DateTimeField(null=True, blank=True)
    # Phase 10.4: category-specific metadata (e.g. vehicle year/make, clothing size, book ISBN)
    extra_data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Listing'
        verbose_name_plural = 'Listings'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.title[:50]} | {self.owner.username}"

    def save(self, *args, **kwargs):
        # Auto-set 30-day expiry on first save
        if not self.pk and self.expires_at is None:
            self.expires_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.expires_at is not None and timezone.now() > self.expires_at

    @property
    def can_bump(self):
        if not self.bumped_at:
            return True
        return (timezone.now() - self.bumped_at).days >= 7


class SavedListing(models.Model):
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_listings')
    listing = models.ForeignKey('Listing', on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'listing')
        ordering = ['-saved_at']
        verbose_name = 'Saved Listing'
        verbose_name_plural = 'Saved Listings'

    def __str__(self):
        return f"{self.user.username} saved {self.listing.title[:40]}"


class Follow(models.Model):
    follower  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')
        verbose_name = 'Follow'
        verbose_name_plural = 'Follows'

    def __str__(self):
        return f"{self.follower.username} → {self.following.username}"


class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='conversations')
    listing      = models.ForeignKey('Listing', on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        return f"Conversation {self.pk}"


class ChatMessage(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_chat_messages')
    body         = models.TextField(blank=True)
    attachment   = models.FileField(upload_to='chat_attachments/', blank=True, null=True)
    sent_at      = models.DateTimeField(auto_now_add=True, db_index=True)
    read         = models.BooleanField(default=False)

    class Meta:
        ordering = ['sent_at']
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'

    def __str__(self):
        return f"{self.sender.username}: {self.body[:40] or '[attachment]'}"


class Review(models.Model):
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_given')
    seller   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews_received')
    rating   = models.PositiveSmallIntegerField(choices=[(i, i) for i in range(1, 6)])
    body     = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('reviewer', 'seller')
        ordering = ['-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'

    def __str__(self):
        return f"{self.reviewer.username} → {self.seller.username}: {self.rating}★"


class Offer(models.Model):
    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
    ]
    listing    = models.ForeignKey('Listing', on_delete=models.CASCADE, related_name='offers')
    buyer      = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='offers_made')
    amount     = models.DecimalField(max_digits=10, decimal_places=2)
    message    = models.TextField(blank=True)
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Offer'
        verbose_name_plural = 'Offers'

    def __str__(self):
        return f"{self.buyer.username} offered ${self.amount} on '{self.listing.title[:40]}' [{self.status}]"


class PriceAlert(models.Model):
    user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='price_alerts')
    listing     = models.ForeignKey('Listing', on_delete=models.CASCADE, related_name='price_alerts')
    alert_below = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    triggered   = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'listing')
        verbose_name = 'Price Alert'
        verbose_name_plural = 'Price Alerts'

    def __str__(self):
        threshold = f"below ${self.alert_below}" if self.alert_below else "any drop"
        return f"{self.user.username} watching '{self.listing.title[:40]}' ({threshold})"


class ListingView(models.Model):
    listing    = models.ForeignKey('Listing', on_delete=models.CASCADE, related_name='views')
    viewer     = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='listing_views')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    viewed_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Listing View'
        verbose_name_plural = 'Listing Views'

    def __str__(self):
        who = self.viewer.username if self.viewer else self.ip_address or 'anonymous'
        return f"{who} viewed '{self.listing.title[:40]}'"


# ── Signals ────────────────────────────────────────────────────────────────────

@receiver(pre_save, sender=Listing)
def check_price_drop_alerts(sender, instance, **kwargs):
    """Trigger PriceAlerts when a listing's price is lowered."""
    if not instance.pk:
        return  # New listing — no alerts yet
    try:
        old_price = Listing.objects.values_list('price', flat=True).get(pk=instance.pk)
    except Listing.DoesNotExist:
        return
    if instance.price < old_price:
        PriceAlert.objects.filter(
            listing_id=instance.pk,
            triggered=False,
        ).filter(
            Q(alert_below__isnull=True) | Q(alert_below__gte=instance.price)
        ).update(triggered=True)


# Legacy direct messaging (pre-Phase 6) — kept for migration continuity
class Thread(models.Model):
    sender   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_threads')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_threads')

    class Meta:
        verbose_name = 'Thread'
        verbose_name_plural = 'Threads'

    def __str__(self):
        return f"Thread: {self.sender.username} → {self.receiver.username}"


class Message(models.Model):
    thread        = models.ForeignKey('Thread', on_delete=models.CASCADE, related_name='messages', blank=True, null=True)
    sender_acc    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver_acc  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message_text  = models.CharField(max_length=10000)
    message_image = models.ImageField(upload_to='message_images', blank=True, null=True)
    timestamp     = models.DateTimeField(default=timezone.now, db_index=True)
    delivered     = models.BooleanField(default=False)
    read          = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender_acc.username} → {self.receiver_acc.username}: {self.message_text[:40]}"
