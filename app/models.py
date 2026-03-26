from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, primary_key=True, verbose_name='user', related_name='profile', on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='pfps', default='pfps/default_pfp.png')
    location = models.CharField(max_length=100, blank=True, null=True)
    about = models.TextField(max_length=500, blank=True, null=True)

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


class Listing(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='listing_images', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    caption = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'Listing'
        verbose_name_plural = 'Listings'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.title[:50]} | {self.owner.username}"


class SavedListing(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_listings')
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


# Legacy direct messaging (pre-Phase 6) — kept for migration continuity
class Thread(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_threads')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_threads')

    class Meta:
        verbose_name = 'Thread'
        verbose_name_plural = 'Threads'

    def __str__(self):
        return f"Thread: {self.sender.username} → {self.receiver.username}"


class Message(models.Model):
    thread = models.ForeignKey('Thread', on_delete=models.CASCADE, related_name='messages', blank=True, null=True)
    sender_acc = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver_acc = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    message_text = models.CharField(max_length=10000)
    message_image = models.ImageField(upload_to='message_images', blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    delivered = models.BooleanField(default=False)
    read = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender_acc.username} → {self.receiver_acc.username}: {self.message_text[:40]}"
