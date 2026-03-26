from django import forms
from .models import Listing, Category

class ListingForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label='— Select a category —',
    )

    class Meta:
        model = Listing
        fields = ['title', 'category', 'price', 'caption', 'image']