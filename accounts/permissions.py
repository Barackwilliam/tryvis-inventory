"""Access control for the inventory system."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from accounts.models import user_is_manager


def inventory_required(view):
    """Any active, logged-in user of this system."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        return view(request, *args, **kwargs)

    return wrapper


def manager_required(view):
    """Costs, purchases, reports and setup screens."""

    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not user_is_manager(request.user):
            raise PermissionDenied("This area is restricted to the Manager.")
        return view(request, *args, **kwargs)

    return wrapper
