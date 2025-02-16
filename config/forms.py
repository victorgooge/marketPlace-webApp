from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms

class SignUpForm(UserCreationForm):
    # Auto Focus
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'autofocus': True})
    )

    class Meta:
        model = User
        fields = [
            'first_name',
            'last_name',
            'email',
            'username',
            'password1',
            'password2',
        ]
