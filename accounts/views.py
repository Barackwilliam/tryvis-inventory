"""
Managing the people who use the system — inside the system itself, not in
Django's technical admin. The client should never need to see that screen.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.shortcuts import get_object_or_404, redirect, render

from accounts.forms import ManagerSetPasswordForm, UserCreateForm, UserEditForm
from accounts.models import Role
from accounts.permissions import manager_required

User = get_user_model()


@manager_required
def user_list(request):
    people = User.objects.all().order_by("-is_active", "role", "username")
    return render(request, "inventory/user_list.html", {
        "people": people,
        "managers": sum(1 for p in people if p.is_manager and p.is_active),
    })


@manager_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        person = form.save()
        messages.success(
            request,
            f"{person.get_full_name() or person.username} can now sign in as a "
            f"{person.get_role_display().lower()}.",
        )
        return redirect("inventory:user_list")
    return render(request, "inventory/user_form.html", {
        "form": form, "title": "Add a person", "is_new": True,
    })


@manager_required
def user_edit(request, pk):
    person = get_object_or_404(User, pk=pk)
    editing_self = person.pk == request.user.pk

    form = UserEditForm(request.POST or None, instance=person, editing_self=editing_self)
    if request.method == "POST" and form.is_valid():
        # Never leave the system without a manager who can sign in.
        last_manager = (
            person.role == Role.MANAGER
            and person.is_active
            and User.objects.filter(role=Role.MANAGER, is_active=True).count() <= 1
        )
        losing_role = form.cleaned_data.get("role") != Role.MANAGER
        losing_access = not form.cleaned_data.get("is_active", True)

        if last_manager and (losing_role or losing_access):
            messages.error(
                request,
                "This is the only manager who can sign in. Make someone else a "
                "manager first, then change this account.",
            )
        else:
            form.save()
            messages.success(request, f"{person.username} updated.")
            return redirect("inventory:user_list")

    return render(request, "inventory/user_form.html", {
        "form": form, "title": f"Edit {person.username}",
        "person": person, "editing_self": editing_self,
    })


@manager_required
def user_set_password(request, pk):
    """For the day a shopkeeper forgets their password, which will come."""
    person = get_object_or_404(User, pk=pk)
    form = ManagerSetPasswordForm(person, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        if person.pk == request.user.pk:
            update_session_auth_hash(request, person)
        messages.success(
            request, f"New password set for {person.username}. Tell them what it is."
        )
        return redirect("inventory:user_list")
    return render(request, "inventory/user_password.html", {"form": form, "person": person})
