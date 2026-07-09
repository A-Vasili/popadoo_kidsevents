from django.shortcuts import render


def home(request):
    return render(request, "core/index.html")


def gallery(request):
    return render(request, "core/gallery.html")


def about(request):
    return render(request, "core/about.html")


def testimonials(request):
    return render(request, "core/testimonials.html")
