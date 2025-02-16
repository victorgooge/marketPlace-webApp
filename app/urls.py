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

    # Posts
    path('dashboard/listing/create/', create_listing, name='listing-create'),
    path('dashboard/listing/<int:pk>/', listing_detail, name='listing-detail'),
    path('dashboard/listing/<int:pk>/update/', ListingUpdateView.as_view(), name='listing-update'),
    path('dashboard/listing/<int:pk>/delete/', ListingDeleteView.as_view(), name='listing-delete'),
]

