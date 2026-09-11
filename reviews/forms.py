from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    RATING_CHOICES = [
        (5, '★★★★★ (5/5) - Outstanding / Super Clean'),
        (4, '★★★★☆ (4/5) - Very Good'),
        (3, '★★★☆☆ (3/5) - Good / Average'),
        (2, '★★☆☆☆ (2/5) - Needs Improvement'),
        (1, '★☆☆☆☆ (1/5) - Poor'),
    ]

    rating = forms.ChoiceField(
        choices=RATING_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg rounded-pill'}),
        initial=5,
        help_text='Select your rating from 1 to 5 stars'
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control rounded-4',
            'rows': 4,
            'placeholder': 'Tell us about the taste, freshness of ingredients, macros, and overall satisfaction...'
        }),
        min_length=5,
        max_length=1000,
        help_text='Minimum 5 characters'
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']
