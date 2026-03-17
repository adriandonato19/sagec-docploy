from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "debe_cambiar_password", False):
            allowed_paths = {
                reverse("identidad:perfil"),
                reverse("identidad:logout"),
            }
            if request.path not in allowed_paths:
                return redirect("identidad:perfil")

        return self.get_response(request)
