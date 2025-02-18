from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.
class Profile(models.Model):
    user = models.OneToOneField(User, primary_key=True, verbose_name='user', related_name='profile', on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='pfps', default='pfps/default_pfp.png')
    location = models.CharField(max_length=100, blank=True, null=True)
    about = models.TextField(max_length=500, blank=True, null=True)

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
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.TextField()
    image = models.ImageField(upload_to='listing_images', blank=True, null=True)
    price = models.IntegerField()
    caption = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        quarter_cap = len(self.caption) // 4 
        return f"{self.caption[0:quarter_cap]}... | {self.owner.username}"


# Direct Messaging Models - sellers and buyer exchange
class Thread(models.Model): # whole message thread
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+')

class Message(models.Model): # message tokens
    thread = models.ForeignKey('Thread', on_delete=models.CASCADE, related_name='+', blank=True, null=True) # thread can be empty
    sender_acc = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+') # user account sending message
    receiver_acc = models.ForeignKey(User, on_delete=models.CASCADE, related_name='+') # user account recieving message
    messageText = models.CharField(max_length=10000) # sender can type as much as needed
    messageImage = models.ImageField(upload_to='message_images', blank=True, null=True) # TODO: create folder two folders in media: {threadID}/message_images
    timestamp = models.DateTimeField(default=timezone.now)
    delivered = models.BooleanField(default=False)
    read = models.BooleanField(default=False)

    

