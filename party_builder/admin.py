from django.contrib import admin

from .models import AddonExperience, PartyBuild, PartyBuildAddon, PartyPackage


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
        "package",
        "guest_count",
        "total_price",
        "status",
        "created_at",
    )
    list_filter = ("status", "event_date", "package")
    search_fields = (
        "contact_name",
        "contact_email",
        "contact_phone",
        "public_id",
    )
    readonly_fields = (
        "public_id",
        "package",
        "total_price",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    inlines = (PartyBuildAddonInline,)
