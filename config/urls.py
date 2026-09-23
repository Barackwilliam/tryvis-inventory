from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from core import views as core_views

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="inventory:dashboard", permanent=False)),
    path("login/", auth_views.LoginView.as_view(
        template_name="inventory/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("password/change/", auth_views.PasswordChangeView.as_view(
        template_name="inventory/password_change.html", success_url="/"), name="password_change"),
    # Public on purpose: this is how the support assistant is trained.
    # It contains no business data, only how the system works.
    path("help/knowledge.txt", core_views.knowledge_base, name="knowledge_base"),
    path("help/assistant.txt", core_views.assistant_persona, name="assistant_persona"),
    path("admin/", admin.site.urls),
    path("app/", include("config.app_urls")),
]

admin.site.site_header = "Tryvis Inventory Administration"
admin.site.site_title = "Tryvis Inventory"
admin.site.index_title = "System setup"
