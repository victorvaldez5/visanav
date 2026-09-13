from django.contrib import admin

from .models import Conversation, Message, Feedback

# Register your models here.
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(Feedback)
