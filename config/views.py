from django.shortcuts import render, redirect, HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout

from config.forms import SignUpForm

# For Email Verification
from django.contrib.sites.shortcuts import get_current_site  
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode  
from django.template.loader import render_to_string     
from django.core.mail import EmailMessage
from django.contrib.auth import get_user_model, backends
from django.db.models import Q
from django.http import HttpResponse
from .tokens import account_activation_token 


# Create your views here.

# Sign-Up 
def signup(request):
    form = SignUpForm()
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            current_site = get_current_site(request)
            mail_subject = 'Activate your account'
            message = render_to_string('registration/email_template/acc_activation_email.html', {
                        'request':request,
                        'user': user,
                        'domain': current_site.domain,
                        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                        'token': account_activation_token.make_token(user),
                    })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(mail_subject, message, to=[to_email])
            email.send()
            # Redirect user to login, flash message prompting user to activate account sent to email
            messages.info(request, "Confirmation email sent. Please check to activate your account.")
            return redirect('login')
    return render(request, 'registration/signup.html', {'form':form})

# Account Activation
def activate(request, uidb64, token):
    User = get_user_model()
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        return HttpResponse('Thank you for your email confirmation. You can now login to your account.')
    else:
        return HttpResponse('Activation link is invalid!')

# Login
def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username-email')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('feed')
        else:
            messages.info(request, "Incorrect username or password")
            return redirect('login')
    return render(request, 'registration/login.html')

# Logout
def user_logout(request):
    logout(request)
    return redirect('login')


