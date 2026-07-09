# This file controls the public information pages of the website.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.shortcuts import render


def home(request):
    return render(request, "core/index.html")


# This view renders the public gallery page.
def gallery(request):
    return render(request, "core/gallery.html")


# This view renders the public About Us page.
def about(request):
    return render(request, "core/about.html")


# This view renders the public testimonials page.
def testimonials(request):
    return render(request, "core/testimonials.html")
