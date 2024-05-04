from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin

from .models import *
from .forms import ListingForm

# Create your views here.

# Landing Page
class HomePage(TemplateView):
    template_name = 'app/_index.html'

# Listings/Feec
def feed_listings(request):
    all_listings = Listing.objects.all().order_by('-timestamp')
    profiles = Profile.objects.all()
    context = {
        'all_listings':all_listings,
        'profiles':profiles,
    }
    return render(request, 'app/feed.html', context)

# User Dashboard
@login_required(login_url='login')
def dashboard(request):
    profile = Profile.objects.get(user=request.user)
    user_listings = Listing.objects.filter(owner=request.user).order_by('-timestamp')
    context = {
        'profile':profile,
        'user_listings':user_listings,
    }
    return render(request, 'app/dashboard.html', context)


''' LISTING POSTS '''
# Lisitng Creation 
def create_listing(request):
    all_listings = Listing.objects.all().order_by('-timestamp')
    form = ListingForm(request.POST)

    if form.is_valid():
        new_listing = form.save(commit=False)
        new_listing.owner = request.user
        new_listing.save()
        return redirect('dashboard-home')

    context = {
        'all_listings':all_listings,
        'form':form,
        'create':True,
    }
    return render(request, 'app/listing_form.html', context)
    
# Listing Details
def listing_detail(request, pk):
    listing = Listing.objects.get(pk=pk)
    profile = Profile.objects.get(user=listing.owner)

    context = {
        'listing':listing,
        'profile':profile,
    }
    return render(request, 'app/listing_detail.html', context)

# Listing Edit
class ListingUpdateView(UserPassesTestMixin, LoginRequiredMixin, UpdateView):
    model = Listing
    fields = ['title', 'image', 'price', 'caption']
    success_url = reverse_lazy('dashboard-home')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        listing = self.get_object()
        return self.request.user == listing.owner
    
# Listing Deletion
class ListingDeleteView(UserPassesTestMixin, LoginRequiredMixin, DeleteView):
    model = Listing
    success_url = reverse_lazy('dashboard-home')

    def test_func(self):
        listing = self.get_object()
        return self.request.user == listing.owner   


''' PROFILES '''
class ProfileUpdateView(UserPassesTestMixin, LoginRequiredMixin, UpdateView):
    model = Profile
    fields = ['profile_picture', 'location', 'about']
    success_url = reverse_lazy('dashboard-home')

    def test_func(self):
        profile = self.get_object()
        return self.request.user == profile.user

