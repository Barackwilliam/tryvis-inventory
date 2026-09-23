"""
The help knowledge base, served as plain text.

JamiiBot is trained by pointing it at a link, so the system publishes its own
help material. One source of truth: change a feature, regenerate the file, and
the bot's training is already correct. No second copy quietly going stale.

The page carries no business data at all — only how the system works — so it is
open by default. Set HELP_DOC_TOKEN to require ?k=<token> if you would rather
keep the link private.
"""
from datetime import datetime, timezone as utc
from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.views.decorators.cache import cache_control

DOCS = Path(settings.BASE_DIR) / "docs"
KNOWLEDGE = DOCS / "knowledge_base.md"
PERSONA = DOCS / "assistant_persona.md"


def _serve(path, title):
    if not path.exists():
        raise Http404("That document has not been written yet.")

    stamp = timezone.localtime(datetime.fromtimestamp(path.stat().st_mtime, tz=utc.utc))
    header = (
        f"# {settings.COMPANY_NAME} — {title}\n"
        f"# Last updated: {stamp:%d %B %Y, %H:%M} East Africa time\n\n"
    )
    response = HttpResponse(
        header + path.read_text(encoding="utf-8"),
        content_type="text/plain; charset=utf-8",
    )
    response["X-Robots-Tag"] = "noindex"
    return response


def _guard(request):
    token = getattr(settings, "HELP_DOC_TOKEN", "")
    if token and request.GET.get("k") != token:
        raise Http404("Not found.")


@cache_control(max_age=600, public=True)
def knowledge_base(request):
    """The questions and answers. This is what JamiiBot is trained on."""
    _guard(request)
    return _serve(KNOWLEDGE, "Inventory system help")


@cache_control(max_age=600, public=True)
def assistant_persona(request):
    """
    How the assistant must behave. This belongs in JamiiBot's system prompt,
    not in its training documents — it has to apply to every message, not only
    when a question happens to match it.
    """
    _guard(request)
    return _serve(PERSONA, "Support assistant — system prompt")
