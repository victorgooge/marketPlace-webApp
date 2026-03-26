import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Q, Count
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .models import Listing, Profile, Thread, Message, SavedListing, Follow, Conversation, ChatMessage
from .forms import ListingForm

User = get_user_model()


# Landing Page
class HomePage(TemplateView):
    template_name = 'app/_index.html'


# Listings / Feed
def feed_listings(request):
    listing_qs = Listing.objects.select_related('owner__profile').order_by('-timestamp')
    paginator = Paginator(listing_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    saved_ids = set()
    if request.user.is_authenticated:
        saved_ids = set(SavedListing.objects.filter(user=request.user).values_list('listing_id', flat=True))

    return render(request, 'app/feed.html', {'page_obj': page_obj, 'saved_ids': saved_ids})


# User Dashboard
@login_required
def dashboard(request):
    profile = get_object_or_404(Profile, user=request.user)
    user_listings = Listing.objects.filter(owner=request.user).order_by('-timestamp')
    annotated_user = User.objects.annotate(
        follower_count=Count('followers', distinct=True),
        following_count=Count('following', distinct=True),
    ).get(pk=request.user.pk)
    return render(request, 'app/dashboard.html', {
        'profile':      profile,
        'user_listings': user_listings,
        'follower_count':  annotated_user.follower_count,
        'following_count': annotated_user.following_count,
    })


''' LISTING POSTS '''

# Listing Creation
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


# Listing Details
def listing_detail(request, pk):
    listing = get_object_or_404(Listing.objects.select_related('owner__profile'), pk=pk)
    owner   = listing.owner
    is_saved = (request.user.is_authenticated and
                SavedListing.objects.filter(user=request.user, listing=listing).exists())
    is_following = (
        request.user.is_authenticated and
        request.user != owner and
        Follow.objects.filter(follower=request.user, following=owner).exists()
    )
    follower_count = owner.followers.count()
    return render(request, 'app/listing_detail.html', {
        'listing':        listing,
        'profile':        owner.profile,
        'is_saved':       is_saved,
        'is_following':   is_following,
        'follower_count': follower_count,
    })


# Listing Edit
class ListingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Listing
    fields = ['title', 'image', 'price', 'caption']
    success_url = reverse_lazy('dashboard-home')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def test_func(self):
        return self.request.user == self.get_object().owner


# Listing Deletion
class ListingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Listing
    success_url = reverse_lazy('dashboard-home')

    def test_func(self):
        return self.request.user == self.get_object().owner


''' PROFILES '''

class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Profile
    fields = ['profile_picture', 'location', 'about']
    success_url = reverse_lazy('dashboard-home')

    def test_func(self):
        return self.request.user == self.get_object().user


''' SEARCH '''

_SORT_MAP = {
    'newest':     '-timestamp',
    'oldest':     'timestamp',
    'price_asc':  'price',
    'price_desc': '-price',
}

def search_view(request):
    """
    Full-text listing search using Q objects on title + caption.
    TODO: swap Q filters for SearchVector/SearchQuery when migrating to PostgreSQL,
          or integrate Meilisearch/Elasticsearch for large datasets.
    """
    query     = request.GET.get('q', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    sort      = request.GET.get('sort', 'newest')

    listings = Listing.objects.select_related('owner__profile')

    if query:
        listings = listings.filter(
            Q(title__icontains=query) |
            Q(caption__icontains=query)
        )

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

    listings = listings.order_by(_SORT_MAP.get(sort, '-timestamp'))

    result_count = listings.count()
    paginator = Paginator(listings, 20)
    page_obj  = paginator.get_page(request.GET.get('page'))

    saved_ids = set()
    if request.user.is_authenticated:
        saved_ids = set(SavedListing.objects.filter(user=request.user).values_list('listing_id', flat=True))

    sort_choices = [
        ('newest',     'Newest'),
        ('oldest',     'Oldest'),
        ('price_asc',  'Price: Low → High'),
        ('price_desc', 'Price: High → Low'),
    ]

    return render(request, 'app/search.html', {
        'page_obj':     page_obj,
        'query':        query,
        'min_price':    min_price,
        'max_price':    max_price,
        'sort':         sort,
        'sort_choices': sort_choices,
        'saved_ids':    saved_ids,
        'result_count': result_count,
    })


def search_autocomplete(request):
    """Return up to 8 matching listing titles as JSON for the navbar autocomplete."""
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    titles = (Listing.objects
              .filter(title__icontains=q)
              .values_list('title', flat=True)
              .distinct()
              .order_by('title')[:8])

    return JsonResponse({'results': list(titles)})


''' SAVED LISTINGS '''

@login_required
def save_listing_toggle(request, pk):
    """Toggle save/unsave a listing. Returns JSON {saved: bool, count: int}."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    listing = get_object_or_404(Listing, pk=pk)
    saved_obj, created = SavedListing.objects.get_or_create(user=request.user, listing=listing)

    if not created:
        saved_obj.delete()
        saved = False
    else:
        saved = True

    count = listing.saved_by.count()
    return JsonResponse({'saved': saved, 'count': count})


@login_required
def saved_listings_page(request):
    """Show all listings saved by the current user."""
    saved = (SavedListing.objects
             .filter(user=request.user)
             .select_related('listing__owner__profile')
             .order_by('-saved_at'))
    return render(request, 'app/saved_listings.html', {'saved': saved})


''' FOLLOW SELLERS '''

@login_required
def follow_toggle(request, username):
    """Toggle follow/unfollow a seller. Returns JSON {following: bool, follower_count: int}."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    target = get_object_or_404(User, username=username)

    if target == request.user:
        return JsonResponse({'error': 'Cannot follow yourself'}, status=400)

    follow_obj, created = Follow.objects.get_or_create(follower=request.user, following=target)

    if not created:
        follow_obj.delete()
        following = False
    else:
        following = True

    follower_count = target.followers.count()
    return JsonResponse({'following': following, 'follower_count': follower_count})


def public_profile(request, username):
    """Public profile page for any user."""
    profile_user = get_object_or_404(
        User.objects.annotate(
            follower_count=Count('followers', distinct=True),
            following_count=Count('following', distinct=True),
        ),
        username=username,
    )
    profile     = get_object_or_404(Profile, user=profile_user)
    listings    = Listing.objects.filter(owner=profile_user).order_by('-timestamp')
    is_following = (
        request.user.is_authenticated and
        request.user != profile_user and
        Follow.objects.filter(follower=request.user, following=profile_user).exists()
    )
    return render(request, 'app/profile.html', {
        'profile_user':   profile_user,
        'profile':        profile,
        'listings':       listings,
        'is_following':   is_following,
    })


''' MESSAGING '''

@login_required
def inbox_view(request):
    """List all conversations for the current user, newest first."""
    conversations = (Conversation.objects
                     .filter(participants=request.user)
                     .prefetch_related('participants__profile', 'messages')
                     .order_by('-updated_at'))

    # Attach other participant and last message to each conversation
    conv_data = []
    for conv in conversations:
        other = conv.participants.exclude(pk=request.user.pk).first()
        last_msg = conv.messages.order_by('-sent_at').first()
        unread = conv.messages.filter(read=False).exclude(sender=request.user).count()
        conv_data.append({
            'conv':     conv,
            'other':    other,
            'last_msg': last_msg,
            'unread':   unread,
        })

    return render(request, 'app/inbox.html', {'conv_data': conv_data})


@login_required
def chatroom_view(request, pk):
    """Show a single conversation's chat room."""
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants__profile'),
        pk=pk,
        participants=request.user,
    )
    other = conversation.participants.exclude(pk=request.user.pk).first()

    # Mark incoming messages as read
    (ChatMessage.objects
     .filter(conversation=conversation, read=False)
     .exclude(sender=request.user)
     .update(read=True))

    return render(request, 'app/chatroom.html', {
        'conversation': conversation,
        'other':        other,
    })


_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB

@login_required
def send_attachment(request, pk):
    """Accept a file upload (+ optional text body), save it as a ChatMessage,
    and broadcast to all WebSocket clients in the conversation group."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants'),
        pk=pk,
        participants=request.user,
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
    conversation.save()  # bump updated_at so inbox sorts correctly

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
        f'chat_{pk}',
        {'type': 'chat_message', 'message': serialized},
    )

    return JsonResponse({'ok': True, 'message': serialized})


@login_required
def start_conversation(request, listing_pk):
    """Find or create a conversation between the current user and the listing's seller."""
    listing = get_object_or_404(Listing, pk=listing_pk)
    seller  = listing.owner

    if seller == request.user:
        return redirect('listing-detail', pk=listing_pk)

    # Find existing conversation for this listing between these two users
    conv = (Conversation.objects
            .filter(participants=request.user)
            .filter(participants=seller)
            .filter(listing=listing)
            .first())

    if not conv:
        conv = Conversation.objects.create(listing=listing)
        conv.participants.add(request.user, seller)

    return redirect('chatroom', pk=conv.pk)
