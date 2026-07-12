
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, TemplateView

from party_builder.models import PartyBuild

from .forms import PopadooAuthenticationForm, ProfileForm, SignUpForm
from .models import CustomerProfile


class SignUpView(FormView):
    template_name = "accounts/sign_up.html"
    form_class = SignUpForm
    success_url = reverse_lazy("accounts:accounts_customer_dashboard")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("accounts:accounts_customer_dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, "Your account is ready. Welcome to Popadoo.")
        return super().form_valid(form)


class SignInView(LoginView):
    template_name = "accounts/sign_in.html"
    authentication_form = PopadooAuthenticationForm
    redirect_authenticated_user = True


class SignOutView(LogoutView):
    next_page = reverse_lazy("core:core_home")
    http_method_names = ["post", "options"]


class ProfileUpdateView(LoginRequiredMixin, FormView):
    template_name = "accounts/profile.html"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:accounts_profile")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        profile, _ = CustomerProfile.objects.get_or_create(user=self.request.user)
        kwargs["instance"] = profile
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Your saved details were updated.")
        return super().form_valid(form)


class CustomerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bookings"] = (
            PartyBuild.objects.filter(customer=self.request.user)
            .select_related("package", "guest_tier")
            .prefetch_related("addon_items__addon")[:20]
        )
        return context
