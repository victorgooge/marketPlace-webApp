from django.contrib import admin

from .models import *

# Register your models here.
admin.site.register(Profile)
admin.site.register(Listing)
admin.site.register(Thread)
admin.site.register(Message)