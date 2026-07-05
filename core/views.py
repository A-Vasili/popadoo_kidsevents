from django.shortcuts import render


def home(request):
    return render(request, "core/index.html")


def gallery(request):
    return render(request, "core/gallery.html")


def packages(request):
    return render(request, "core/packages.html")


def about(request):
    return render(request, "core/about.html")


def testimonials(request):
    return render(request, "core/testimonials.html")


def contact(request):
    return render(request, "core/contact.html")