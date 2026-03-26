from django.contrib import admin
from .models import (
    Profile, Category, Listing, SavedListing, Follow,
    Conversation, ChatMessage, Review,
    Offer, PriceAlert, ListingView,
    Thread, Message,
)

admin.site.register(Category)
admin.site.register(Profile)
admin.site.register(Listing)
admin.site.register(SavedListing)
admin.site.register(Follow)
admin.site.register(Conversation)
admin.site.register(ChatMessage)
admin.site.register(Review)
admin.site.register(Offer)
admin.site.register(PriceAlert)
admin.site.register(ListingView)
admin.site.register(Thread)
admin.site.register(Message)
