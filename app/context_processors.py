def unread_messages_count(request):
    """Inject unread chat message count into every template context."""
    if request.user.is_authenticated:
        from .models import ChatMessage
        count = (ChatMessage.objects
                 .filter(conversation__participants=request.user, read=False)
                 .exclude(sender=request.user)
                 .count())
        return {'unread_count': count}
    return {'unread_count': 0}
