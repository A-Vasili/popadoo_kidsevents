from django.contrib import admin

from .models import (
    AddonExperience,
    GuestPriceTier,
    PartyBuild,
    PartyBuildAddon,
    PartyPackage,
)


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


class PartyBuildAddonInline(admin.TabularInline):
    model = PartyBuildAddon
    extra = 0
    can_delete = False
    readonly_fields = ("addon", "unit_price")


@admin.register(PartyBuild)
class PartyBuildAdmin(admin.ModelAdmin):
    list_display = (
        "contact_name",
        "event_date",
        "guest_tier_label",
        "guest_count",
        "total_price",
        "payment_status",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        "payment_status",
        "event_date",
        "package",
        "guest_tier",
    )
    search_fields = (
        "contact_name",
        "contact_email",
        "contact_phone",
        "public_id",
        "payment_reference",
    )
    readonly_fields = (
        "public_id",
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
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    inlines = (PartyBuildAddonInline,)
