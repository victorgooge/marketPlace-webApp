import os
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Case, When, IntegerField, Value
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import TemplateView, UpdateView, DeleteView

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import (
    Listing, Profile, Thread, Message, SavedListing, Follow,
    Conversation, ChatMessage, Review, Category,
    Offer, PriceAlert, ListingView,
)
from .forms import ListingForm

User = get_user_model()


# ── Landing Page ───────────────────────────────────────────────────────────────

class HomePage(TemplateView):
    template_name = 'app/_index.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('feed')
        return super().dispatch(request, *args, **kwargs)


# ── Feed ───────────────────────────────────────────────────────────────────────

def _active_listings(qs=None):
    """Return a queryset filtered to active, non-expired listings."""
    base = qs if qs is not None else Listing.objects
    now  = timezone.now()
    return base.filter(is_active=True).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    )


def feed_listings(request):
    """
    Personalized feed for authenticated users — floats listings from followed
    sellers and categories the user has saved to the top (priority 0 and 1).
    Falls back to newest-first for unauthenticated users or when no signals exist.
    Category filter (?category=<slug>) can be applied on top.
    """
    category_slug   = request.GET.get('category', '').strip()
    active_category = None
    categories      = Category.objects.all()

    listings = _active_listings().select_related('owner__profile', 'category')

    if category_slug:
        active_category = Category.objects.filter(slug=category_slug).first()
        if active_category:
            listings = listings.filter(category=active_category)

    if request.user.is_authenticated and not category_slug:
        followed_ids = list(
            request.user.following.values_list('following_id', flat=True)
        )
        saved_cat_ids = list(
            request.user.saved_listings
            .exclude(listing__category__isnull=True)
            .values_list('listing__category_id', flat=True)
            .distinct()
        )

        if followed_ids or saved_cat_ids:
            priority = Case(
                When(owner_id__in=followed_ids, then=Value(0)),
                When(category_id__in=saved_cat_ids, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            )
            listings = listings.annotate(priority=priority).order_by('priority', '-timestamp')
        else:
            listings = listings.order_by('-timestamp')

        feed_label = 'For You'
    else:
        listings   = listings.order_by('-timestamp')
        feed_label = 'Recently Listed'

    paginator = Paginator(listings, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    saved_ids = set()
    if request.user.is_authenticated:
        saved_ids = set(
            SavedListing.objects.filter(user=request.user).values_list('listing_id', flat=True)
        )

    return render(request, 'app/feed.html', {
        'page_obj':        page_obj,
        'saved_ids':       saved_ids,
        'feed_label':      feed_label,
        'categories':      categories,
        'active_category': active_category,
        'category_slug':   category_slug,
    })


# ── Dashboard ──────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Seller dashboard — listings with stats, pending offers, price-drop alerts."""
    profile = get_object_or_404(Profile, user=request.user)

    user_listings = (
        Listing.objects
        .filter(owner=request.user)
        .select_related('category')
        .annotate(
            view_count=Count('views', distinct=True),
            save_count=Count('saved_by', distinct=True),
            pending_offer_count=Count(
                'offers',
                filter=Q(offers__status='pending'),
                distinct=True,
            ),
        )
        .order_by('-is_active', '-timestamp')
    )

    pending_offers = (
        Offer.objects
        .filter(listing__owner=request.user, status='pending')
        .select_related('buyer__profile', 'listing')
        .order_by('-created_at')
    )

    # Collect triggered price alerts then clear them so they only show once
    triggered_alerts = list(
        PriceAlert.objects
        .filter(user=request.user, triggered=True)
        .select_related('listing')
    )
    if triggered_alerts:
        PriceAlert.objects.filter(
            user=request.user, triggered=True
        ).update(triggered=False)

    annotated_user = User.objects.annotate(
        follower_count=Count('followers', distinct=True),
        following_count=Count('following', distinct=True),
    ).get(pk=request.user.pk)

    return render(request, 'app/dashboard.html', {
        'profile':          profile,
        'user_listings':    user_listings,
        'pending_offers':   pending_offers,
        'triggered_alerts': triggered_alerts,
        'follower_count':   annotated_user.follower_count,
        'following_count':  annotated_user.following_count,
    })


# ── Listings CRUD ──────────────────────────────────────────────────────────────

@login_required
def create_listing(request):
    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            new_listing = form.save(commit=False)
            new_listing.owner = request.user
            new_listing.save()
            return redirect('dashboard-home')
    else:
        form = ListingForm()
    return render(request, 'app/listing_form.html', {'form': form, 'create': True})


def listing_detail(request, pk):
    """Listing detail page — tracks a view per session, provides offer/alert context."""
    listing = get_object_or_404(
        Listing.objects.select_related('owner__profile', 'category'), pk=pk
    )
    owner = listing.owner

    # Track view (once per session per listing)
    session_key = f'viewed_{pk}'
    if not request.session.get(session_key):
        raw_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        ip = raw_ip.split(',')[0].strip() or None
        ListingView.objects.create(
            listing=listing,
            viewer=request.user if request.user.is_authenticated else None,
            ip_address=ip,
        )
        request.session[session_key] = True

    is_saved = (
        request.user.is_authenticated and
        SavedListing.objects.filter(user=request.user, listing=listing).exists()
    )
    is_following = (
        request.user.is_authenticated and
        request.user != owner and
        Follow.objects.filter(follower=request.user, following=owner).exists()
    )
    follower_count = owner.followers.count()
    rating_data = (
        Review.objects.filter(seller=owner)
        .aggregate(avg=Avg('rating'), count=Count('id'))
    )
    view_count = listing.views.count()

    # Buyer-facing offer/alert context
    existing_offer = None
    has_alert      = False
    if request.user.is_authenticated and request.user != owner:
        existing_offer = Offer.objects.filter(listing=listing, buyer=request.user).first()
        has_alert      = PriceAlert.objects.filter(listing=listing, user=request.user).exists()

    # Owner-facing: pending offers on this listing
    pending_offers = []
    if request.user == owner:
        pending_offers = (
            Offer.objects
            .filter(listing=listing, status='pending')
            .select_related('buyer__profile')
        )

    return render(request, 'app/listing_detail.html', {
        'listing':             listing,
        'profile':             owner.profile,
        'is_saved':            is_saved,
        'is_following':        is_following,
        'follower_count':      follower_count,
        'seller_avg_rating':   rating_data['avg'],
        'seller_review_count': rating_data['count'],
        'view_count':          view_count,
        'existing_offer':      existing_offer,
        'has_alert':           has_alert,
        'pending_offers':      pending_offers,
    })


class ListingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model      = Listing
    fields     = ['title', 'category', 'image', 'price', 'caption']
    success_url = reverse_lazy('dashboard-home')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        return self.request.user == self.get_object().owner


class ListingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model       = Listing
    success_url = reverse_lazy('dashboard-home')

    def test_func(self):
        return self.request.user == self.get_object().owner


# ── Mark as Sold ───────────────────────────────────────────────────────────────

@login_required
def mark_as_sold(request, pk):
    """Mark a listing inactive. Prompts the seller to review the buyer if an offer was accepted."""
    if request.method != 'POST':
        return redirect('listing-detail', pk=pk)

    listing = get_object_or_404(Listing, pk=pk, owner=request.user)
    listing.is_active = False
    listing.save()
    messages.success(request, f'"{listing.title}" has been marked as sold.')

    accepted = Offer.objects.filter(listing=listing, status='accepted').first()
    if accepted:
        messages.info(
            request,
            f'Consider leaving a review for {accepted.buyer.username} on their profile.'
        )

    return redirect('dashboard-home')


# ── Bump Listing ───────────────────────────────────────────────────────────────

@login_required
def bump_listing(request, pk):
    """Bring a listing back to the top of the feed. Allowed once every 7 days."""
    if request.method != 'POST':
        return redirect('listing-detail', pk=pk)

    listing = get_object_or_404(Listing, pk=pk, owner=request.user, is_active=True)

    if not listing.can_bump:
        days_left = 7 - (timezone.now() - listing.bumped_at).days
        messages.error(
            request,
            f'You can bump this listing again in {days_left} day{"s" if days_left != 1 else ""}.'
        )
        return redirect('dashboard-home')

    now = timezone.now()
    listing.timestamp  = now
    listing.bumped_at  = now
    listing.expires_at = now + timedelta(days=30)
    listing.save()
    messages.success(request, f'"{listing.title}" has been bumped to the top of the feed.')
    return redirect('dashboard-home')


# ── Profiles ───────────────────────────────────────────────────────────────────

class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model       = Profile
    fields      = ['profile_picture', 'cover_photo', 'location', 'about', 'website']
    success_url = reverse_lazy('dashboard-home')

    def test_func(self):
        return self.request.user == self.get_object().user


# ── Search ─────────────────────────────────────────────────────────────────────

_SORT_MAP = {
    'newest':     '-timestamp',
    'oldest':     'timestamp',
    'price_asc':  'price',
    'price_desc': '-price',
}


def search_view(request):
    """
    Full-text listing search using Q objects on title + caption.
    Supports category, price range, and sort filters via query params.
    TODO: swap Q filters for SearchVector/SearchQuery when migrating to PostgreSQL,
          or integrate Meilisearch/Elasticsearch for large datasets.
    """
    query         = request.GET.get('q', '').strip()
    min_price     = request.GET.get('min_price', '').strip()
    max_price     = request.GET.get('max_price', '').strip()
    sort          = request.GET.get('sort', 'newest')
    category_slug = request.GET.get('category', '').strip()

    listings = _active_listings().select_related('owner__profile', 'category')

    if query:
        listings = listings.filter(
            Q(title__icontains=query) | Q(caption__icontains=query)
        )
    if category_slug:
        listings = listings.filter(category__slug=category_slug)
    if min_price:
        try:
            listings = listings.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            listings = listings.filter(price__lte=float(max_price))
        except ValueError:
            pass

    listings     = listings.order_by(_SORT_MAP.get(sort, '-timestamp'))
    result_count = listings.count()
    paginator    = Paginator(listings, 20)
    page_obj     = paginator.get_page(request.GET.get('page'))

    saved_ids = set()
    if request.user.is_authenticated:
        saved_ids = set(
            SavedListing.objects.filter(user=request.user).values_list('listing_id', flat=True)
        )

    sort_choices = [
        ('newest',     'Newest'),
        ('oldest',     'Oldest'),
        ('price_asc',  'Price: Low → High'),
        ('price_desc', 'Price: High → Low'),
    ]

    return render(request, 'app/search.html', {
        'page_obj':        page_obj,
        'query':           query,
        'min_price':       min_price,
        'max_price':       max_price,
        'sort':            sort,
        'sort_choices':    sort_choices,
        'saved_ids':       saved_ids,
        'result_count':    result_count,
        'categories':      Category.objects.all(),
        'category_slug':   category_slug,
    })


def search_autocomplete(request):
    """Return up to 8 matching listing titles as JSON for the navbar autocomplete."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    titles = (
        _active_listings()
        .filter(title__icontains=q)
        .values_list('title', flat=True)
        .distinct()
        .order_by('title')[:8]
    )
    return JsonResponse({'results': list(titles)})


# ── Saved Listings ─────────────────────────────────────────────────────────────

@login_required
def save_listing_toggle(request, pk):
    """Toggle save/unsave a listing. Returns JSON {saved: bool, count: int}."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    listing   = get_object_or_404(Listing, pk=pk)
    obj, created = SavedListing.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        obj.delete()
        saved = False
    else:
        saved = True

    return JsonResponse({'saved': saved, 'count': listing.saved_by.count()})


@login_required
def saved_listings_page(request):
    """Show all listings saved by the current user."""
    saved = (
        SavedListing.objects
        .filter(user=request.user)
        .select_related('listing__owner__profile')
        .order_by('-saved_at')
    )
    return render(request, 'app/saved_listings.html', {'saved': saved})


# ── Follow Sellers ─────────────────────────────────────────────────────────────

@login_required
def follow_toggle(request, username):
    """Toggle follow/unfollow a seller. Returns JSON {following: bool, follower_count: int}."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    target = get_object_or_404(User, username=username)
    if target == request.user:
        return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

    obj, created = Follow.objects.get_or_create(follower=request.user, following=target)
    if not created:
        obj.delete()
        following = False
    else:
        following = True

    return JsonResponse({'following': following, 'follower_count': target.followers.count()})


def public_profile(request, username):
    """Public profile page for any user."""
    profile_user = get_object_or_404(
        User.objects.annotate(
            follower_count=Count('followers', distinct=True),
            following_count=Count('following', distinct=True),
            avg_rating=Avg('reviews_received__rating'),
            review_count=Count('reviews_received', distinct=True),
        ),
        username=username,
    )
    profile  = get_object_or_404(Profile, user=profile_user)
    listings = Listing.objects.filter(owner=profile_user).order_by('-timestamp')
    reviews  = (
        Review.objects
        .filter(seller=profile_user)
        .select_related('reviewer__profile')
        .order_by('-created_at')
    )

    is_following = (
        request.user.is_authenticated and
        request.user != profile_user and
        Follow.objects.filter(follower=request.user, following=profile_user).exists()
    )

    can_review      = False
    existing_review = None
    if request.user.is_authenticated and request.user != profile_user:
        has_conversation = (
            Conversation.objects
            .filter(participants=request.user)
            .filter(participants=profile_user)
            .exists()
        )
        existing_review = Review.objects.filter(reviewer=request.user, seller=profile_user).first()
        can_review = has_conversation and not existing_review

    return render(request, 'app/profile.html', {
        'profile_user':    profile_user,
        'profile':         profile,
        'listings':        listings,
        'reviews':         reviews,
        'is_following':    is_following,
        'can_review':      can_review,
        'existing_review': existing_review,
    })


# ── Messaging ──────────────────────────────────────────────────────────────────

@login_required
def inbox_view(request):
    """List all conversations for the current user, newest first."""
    conversations = (
        Conversation.objects
        .filter(participants=request.user)
        .prefetch_related('participants__profile', 'messages')
        .order_by('-updated_at')
    )

    conv_data = []
    for conv in conversations:
        other    = conv.participants.exclude(pk=request.user.pk).first()
        last_msg = conv.messages.order_by('-sent_at').first()
        unread   = conv.messages.filter(read=False).exclude(sender=request.user).count()
        conv_data.append({'conv': conv, 'other': other, 'last_msg': last_msg, 'unread': unread})

    return render(request, 'app/inbox.html', {'conv_data': conv_data})


@login_required
def chatroom_view(request, pk):
    """Show a single conversation's chat room."""
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants__profile'),
        pk=pk, participants=request.user,
    )
    other = conversation.participants.exclude(pk=request.user.pk).first()

    ChatMessage.objects.filter(
        conversation=conversation, read=False
    ).exclude(sender=request.user).update(read=True)

    return render(request, 'app/chatroom.html', {
        'conversation': conversation,
        'other':        other,
    })


_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


@login_required
def send_attachment(request, pk):
    """Upload a file (+optional text) as a ChatMessage and broadcast via WebSocket."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants'),
        pk=pk, participants=request.user,
    )

    uploaded_file = request.FILES.get('file')
    body = request.POST.get('body', '').strip()

    if not uploaded_file and not body:
        return JsonResponse({'error': 'No content provided'}, status=400)
    if uploaded_file and uploaded_file.size > _MAX_ATTACHMENT_BYTES:
        return JsonResponse({'error': 'File too large (max 10 MB)'}, status=400)

    msg = ChatMessage.objects.create(
        conversation=conversation,
        sender=request.user,
        body=body,
        attachment=uploaded_file or None,
    )
    conversation.save()

    serialized = {
        'id':              msg.pk,
        'sender':          msg.sender.username,
        'body':            msg.body,
        'sent_at':         msg.sent_at.isoformat(),
        'attachment_url':  msg.attachment.url if msg.attachment else None,
        'attachment_name': os.path.basename(msg.attachment.name) if msg.attachment else None,
    }

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'chat_{pk}', {'type': 'chat_message', 'message': serialized},
    )
    return JsonResponse({'ok': True, 'message': serialized})


@login_required
def start_conversation(request, listing_pk):
    """Find or create a conversation between the current user and the listing's seller."""
    listing = get_object_or_404(Listing, pk=listing_pk)
    seller  = listing.owner

    if seller == request.user:
        return redirect('listing-detail', pk=listing_pk)

    conv = (
        Conversation.objects
        .filter(participants=request.user)
        .filter(participants=seller)
        .filter(listing=listing)
        .first()
    )
    if not conv:
        conv = Conversation.objects.create(listing=listing)
        conv.participants.add(request.user, seller)

    return redirect('chatroom', pk=conv.pk)


# ── Reviews ────────────────────────────────────────────────────────────────────

@login_required
def create_review(request, username):
    """Submit a star rating + optional body for a seller."""
    seller = get_object_or_404(User, username=username)

    if seller == request.user:
        messages.error(request, "You cannot review yourself.")
        return redirect('public-profile', username=username)

    has_conversation = (
        Conversation.objects
        .filter(participants=request.user)
        .filter(participants=seller)
        .exists()
    )
    if not has_conversation:
        messages.error(request, "You can only review sellers you have messaged.")
        return redirect('public-profile', username=username)

    if Review.objects.filter(reviewer=request.user, seller=seller).exists():
        messages.error(request, "You have already reviewed this seller.")
        return redirect('public-profile', username=username)

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', 0))
        except (ValueError, TypeError):
            rating = 0

        if rating not in range(1, 6):
            messages.error(request, "Please select a rating between 1 and 5.")
            return redirect('public-profile', username=username)

        body = request.POST.get('body', '').strip()
        Review.objects.create(reviewer=request.user, seller=seller, rating=rating, body=body)
        messages.success(request, "Your review has been submitted.")

    return redirect('public-profile', username=username)


# ── Offers ─────────────────────────────────────────────────────────────────────

@login_required
def make_offer(request, pk):
    """Submit a price offer on a listing. One offer per buyer per listing."""
    if request.method != 'POST':
        return redirect('listing-detail', pk=pk)

    listing = get_object_or_404(Listing, pk=pk, is_active=True)

    if listing.owner == request.user:
        messages.error(request, "You cannot make an offer on your own listing.")
        return redirect('listing-detail', pk=pk)

    if Offer.objects.filter(listing=listing, buyer=request.user).exists():
        messages.error(request, "You already have an offer on this listing.")
        return redirect('listing-detail', pk=pk)

    try:
        amount = Decimal(request.POST.get('amount', ''))
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        messages.error(request, "Please enter a valid offer amount.")
        return redirect('listing-detail', pk=pk)

    offer_message = request.POST.get('message', '').strip()
    Offer.objects.create(listing=listing, buyer=request.user, amount=amount, message=offer_message)
    messages.success(request, f"Your offer of ${amount} has been sent to the seller.")
    return redirect('listing-detail', pk=pk)


@login_required
def respond_offer(request, offer_pk):
    """Accept or decline an offer. Only the listing owner may respond."""
    if request.method != 'POST':
        return redirect('dashboard-home')

    offer  = get_object_or_404(Offer, pk=offer_pk, listing__owner=request.user, status='pending')
    action = request.POST.get('action')

    if action == 'accept':
        offer.status = 'accepted'
        offer.save()
        messages.success(request, f"Accepted {offer.buyer.username}'s offer of ${offer.amount}.")
    elif action == 'decline':
        offer.status = 'declined'
        offer.save()
        messages.info(request, f"Declined {offer.buyer.username}'s offer.")

    return redirect('dashboard-home')


# ── Price Alerts ───────────────────────────────────────────────────────────────

@login_required
def toggle_price_alert(request, pk):
    """Toggle a price-drop alert for a listing. Returns JSON {active: bool}."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    listing = get_object_or_404(Listing, pk=pk)

    if listing.owner == request.user:
        return JsonResponse({'error': 'Cannot set alert on own listing'}, status=400)

    alert, created = PriceAlert.objects.get_or_create(user=request.user, listing=listing)
    if not created:
        alert.delete()
        active = False
    else:
        active = True

    return JsonResponse({'active': active})
