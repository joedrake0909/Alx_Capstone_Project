from django import forms

class ExampleForm(forms.Form):
    title = forms.CharField(max_length=100, required=True)
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
