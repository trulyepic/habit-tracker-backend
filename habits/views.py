from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import logout, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def _allowed_redirect_hosts():
    """Whitelist local/web frontend hosts for post-auth redirects."""
    hosts = {"localhost:5173", "127.0.0.1:5173"}
    parsed = urlparse(settings.FRONTEND_URL)
    if parsed.netloc:
        hosts.add(parsed.netloc)
    if parsed.hostname:
        hosts.add(parsed.hostname)
    if parsed.hostname and parsed.port:
        hosts.add(f"{parsed.hostname}:{parsed.port}")
    return hosts


def _resolve_frontend_redirect(candidate: str | None) -> str:
    if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts=_allowed_redirect_hosts()):
        return candidate
    return f"{settings.FRONTEND_URL.rstrip('/')}/"


class LoginView(auth_views.LoginView):
    template_name = "login.html"

    def get_success_url_allowed_hosts(self):
        return super().get_success_url_allowed_hosts() | _allowed_redirect_hosts()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["frontend_url"] = f"{settings.FRONTEND_URL.rstrip('/')}/"
        return context


class RegisterView(CreateView):
    form_class = UserCreationForm
    template_name = "register.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response

    def get_success_url(self):
        candidate = self.request.POST.get("next") or self.request.GET.get("next")
        return _resolve_frontend_redirect(candidate)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["frontend_url"] = f"{settings.FRONTEND_URL.rstrip('/')}/"
        context["next"] = _resolve_frontend_redirect(self.request.GET.get("next"))
        return context


@csrf_exempt
@require_POST
def api_logout(request):
    logout(request)
    return JsonResponse({"ok": True})
