import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for a single conversation room.
    Group name: chat_{conversation_id}

    On connect  — verify auth + participation, join group, send message history.
    On receive  — save message to DB, broadcast to group.
    On disconnect — leave group.
    """

    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name      = f'chat_{self.conversation_id}'
        user                 = self.scope['user']

        if not user.is_authenticated:
            await self.close()
            return

        if not await self.is_participant(user, self.conversation_id):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Mark messages from the other side as read
        await self.mark_read(user, self.conversation_id)

        # Send message history on connect
        history = await self.get_history(self.conversation_id)
        await self.send(text_data=json.dumps({'type': 'history', 'messages': history}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)

        # Typing indicator broadcast
        if data.get('type') == 'typing':
            user = self.scope['user']
            await self.channel_layer.group_send(self.group_name, {
                'type':   'typing_indicator',
                'sender': user.username,
            })
            return

        body = data.get('body', '').strip()
        if not body:
            return

        user = self.scope['user']
        msg  = await self.save_message(user, self.conversation_id, body)

        await self.channel_layer.group_send(self.group_name, {
            'type':    'chat_message',
            'message': msg,
        })

    async def chat_message(self, event):
        """Relay a new message to this WebSocket client."""
        await self.send(text_data=json.dumps({
            'type':    'message',
            'message': event['message'],
        }))

    async def typing_indicator(self, event):
        """Relay typing indicator to this WebSocket client."""
        await self.send(text_data=json.dumps({
            'type':   'typing',
            'sender': event['sender'],
        }))

    # ── DB helpers (sync → async) ──────────────────────────

    @database_sync_to_async
    def is_participant(self, user, conversation_id):
        from .models import Conversation
        return Conversation.objects.filter(pk=conversation_id, participants=user).exists()

    @database_sync_to_async
    def get_history(self, conversation_id):
        from .models import ChatMessage
        qs = (ChatMessage.objects
              .filter(conversation_id=conversation_id)
              .select_related('sender')
              .order_by('sent_at')[:100])
        return [self._serialize(m) for m in qs]

    @database_sync_to_async
    def save_message(self, user, conversation_id, body):
        from .models import ChatMessage, Conversation
        conv = Conversation.objects.get(pk=conversation_id)
        msg  = ChatMessage.objects.create(conversation=conv, sender=user, body=body)
        conv.save()  # bump updated_at so inbox sorts correctly
        return self._serialize(msg)

    @database_sync_to_async
    def mark_read(self, user, conversation_id):
        from .models import ChatMessage
        (ChatMessage.objects
         .filter(conversation_id=conversation_id, read=False)
         .exclude(sender=user)
         .update(read=True))

    @staticmethod
    def _serialize(msg):
        return {
            'id':              msg.pk,
            'sender':          msg.sender.username,
            'body':            msg.body,
            'sent_at':         msg.sent_at.isoformat(),
            'attachment_url':  msg.attachment.url if msg.attachment else None,
            'attachment_name': os.path.basename(msg.attachment.name) if msg.attachment else None,
        }
