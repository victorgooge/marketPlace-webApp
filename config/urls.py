"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from .views import *


urlpatterns = [
    path('admin/', admin.site.urls),

    # Sign-Up
    path('signup/', signup, name='signup'),
    path('signup/activate/<uidb64>/<token>/', activate, name='activate'),
    
    # Login
    path('login/', user_login, name='login'),
    path('login/password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/forgot_password/password_reset.html'), name='password_reset'),
    path('login/password-reset-sent/', auth_views.PasswordResetDoneView.as_view(template_name='registration/forgot_password/password_reset_sent.html'), name='password_reset_done'),
    path('login/password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/forgot_password/password_reset_form.html'), name='password_reset_confirm'),
    path('login/password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/forgot_password/password_reset_complete.html'), name='password_reset_complete'),

    # Logout
    path('logout/', user_logout, name='logout'),

    # App Views
    path('', include('app.urls')),
]


# Media Handling
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)