"""Ayudas compartidas por las vistas del panel."""
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def _safe_redirect(request, fallback):
    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback)
