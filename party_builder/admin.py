# This file controls how packages, add-ons, and bookings appear in Django administration.
# Comments in this file explain the purpose of each section without changing how the program works.

from django.contrib import admin

from .models import (
    AddonExperience,
    GuestPriceTier,
    PartyBuild,
    PartyBuildAddon,
    PartyPackage,
)


# This class controls how guest price tier information appears in Django administration.
class GuestPriceTierInline(admin.TabularInline):
    model = GuestPriceTier
    extra = 0
    fields = (
        "label",
        "min_guests",
        "max_guests",
        "total_price",
        "is_default",
        "is_active",
        "display_order",
    )


# This class controls how party package information appears in Django administration.
@admin.register(PartyPackage)
class PartyPackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "base_price",
        "duration_minutes",
        "included_guest_count",
        "is_default",
        "is_active",
    )
    list_filter = ("is_default", "is_active")
    list_editable = ("is_default", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "short_description")
    ordering = ("display_order", "name")
    inlines = (GuestPriceTierInline,)


# This class controls how guest price tier information appears in Django administration.
@admin.register(GuestPriceTier)
class GuestPriceTierAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "package",
        "min_guests",
        "max_guests",
        "total_price",
        "is_default",
        "is_active",
    )
    list_filter = ("package", "is_default", "is_active")
    list_editable = ("total_price", "is_default", "is_active")
    search_fields = ("label", "package__name")
    ordering = ("package", "display_order", "min_guests")


# This class controls how addon experience information appears in Django administration.
@admin.register(AddonExperience)
class AddonExperienceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_minutes",
        "is_featured",
        "is_active",
    )
    list_filter = ("is_featured", "is_active")
    list_editable = ("price", "is_featured", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "short_description")
    ordering = ("display_order", "name")


# This class controls how party build addon information appears in Django administration.
class PartyBuildAddonInline(admin.TabularInline):
    model = PartyBuildAddon
    extra = 0
    can_delete = False
    readonly_fields = ("addon", "unit_price")


# This class controls how party build information appears in Django administration.
@admin.register(PartyBuild)
class PartyBuildAdmin(admin.ModelAdmin):
    list_display = (
        "contact_name",
        "customer",
        "event_date",
        "guest_tier_label",
        "guest_count",
        "total_price",
        "payment_status",
        "status",
        "assignment_state",
        "created_at",
    )
    list_filter = (
        "status",
        "assignment_state",
        "payment_status",
        "event_date",
        "package",
        "guest_tier",
    )
    search_fields = (
        "contact_name",
        "customer",
        "contact_email",
        "contact_phone",
        "public_id",
        "customer",
        "payment_reference",
    )
    readonly_fields = (
        "public_id",
        "customer",
        "package",
        "guest_tier",
        "guest_tier_label",
        "package_price",
        "addon_price",
        "total_price",
        "payment_status",
        "card_brand",
        "card_last_four",
        "payment_reference",
        "checkout_completed_at",
        "assignment_requested_at",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    inlines = (PartyBuildAddonInline,)
