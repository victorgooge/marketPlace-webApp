from django.urls import path

from .views import *

urlpatterns = [
    # Main Home Page
    path('', HomePage.as_view(), name='index'),
    # Feed
    path('explore/', feed_listings, name='feed'),

    # User Dashboard
    path('dashboard/home/', dashboard, name='dashboard-home'),

    # Profile
    path('dashboard/profile/<int:pk>/update/', ProfileUpdateView.as_view(), name='profile-update'),

    # Listings
    path('dashboard/listing/create/', create_listing, name='listing-create'),
    path('dashboard/listing/<int:pk>/', listing_detail, name='listing-detail'),
    path('dashboard/listing/<int:pk>/update/', ListingUpdateView.as_view(), name='listing-update'),
    path('dashboard/listing/<int:pk>/delete/', ListingDeleteView.as_view(), name='listing-delete'),

    # Saved Listings
    path('listings/<int:pk>/save/', save_listing_toggle, name='listing-save'),
    path('saved/', saved_listings_page, name='saved-listings'),

    # Search
    path('search/', search_view, name='search'),
    path('search/autocomplete/', search_autocomplete, name='search-autocomplete'),

    # Follow & Public Profiles
    path('profile/<str:username>/', public_profile, name='public-profile'),
    path('profile/<str:username>/follow/', follow_toggle, name='follow-toggle'),

    # Messaging
    path('messages/', inbox_view, name='inbox'),
    path('messages/<int:pk>/', chatroom_view, name='chatroom'),
    path('messages/<int:pk>/attachment/', send_attachment, name='send-attachment'),
    path('messages/start/<int:listing_pk>/', start_conversation, name='start-conversation'),
]

