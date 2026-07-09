# This file adds role information to every template so navigation can adapt to the signed-in user.
# Comments in this file explain the purpose of each section without changing how the program works.

from .permissions import can_access_operations, can_manage_pricing, is_owner, is_worker


def role_context(request):
    """Expose simple role flags for navigation only; views still enforce permissions."""

    user = request.user
    return {
        "nav_is_owner": is_owner(user),
        "nav_is_worker": is_worker(user),
        "nav_can_access_operations": can_access_operations(user),
        "nav_can_manage_pricing": can_manage_pricing(user),
    }
