"""Views for influencer marketing operations."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import InfluencerProfile, ReferralTransaction


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Renders the influencer dashboard with metrics."""
    profile = get_object_or_404(InfluencerProfile, user=request.user)
    context = {
        "profile": profile,
    }
    return render(request, "influencer/dashboard.html", context)


def referral_page(request: HttpRequest) -> HttpResponse:
    """Public page for a referral code."""
    code = request.GET.get("ref")
    context = {"code": code}
    return render(request, "influencer/referral_page.html", context)


@login_required
def promo_material(request: HttpRequest) -> HttpResponse:
    """Page to download marketing assets."""
    return render(request, "influencer/promo_material.html")


@csrf_exempt
def payment_webhook(request: HttpRequest) -> HttpResponse:
    """Webhook endpoint to record referred sales from MercadoPago."""
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    ref_code = request.GET.get("ref")
    if not ref_code:
        return JsonResponse({"detail": "No referral code"}, status=400)

    profile = get_object_or_404(InfluencerProfile, referral_code=ref_code)

    # parse sale amount from MercadoPago payload (simplified)
    data = request.POST
    sale_amount = float(data.get("sale_amount", 0))
    commission_amount = sale_amount * 0.1  # 10% commission example

    ReferralTransaction.objects.create(
        influencer=profile,
        sale_amount=sale_amount,
        commission_amount=commission_amount,
    )

    profile.total_referred_users = profile.transactions.count()
    profile.total_sales_value += sale_amount
    profile.commission_earned += commission_amount
    profile.wallet_balance += commission_amount
    profile.save(update_fields=[
        "total_referred_users",
        "total_sales_value",
        "commission_earned",
        "wallet_balance",
    ])

    return JsonResponse({"detail": "Transaction recorded"})

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .serializers import InfluencerStatsSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stats(request):
    """Return influencer statistics in JSON format."""
    serializer = InfluencerStatsSerializer(request.user.influencer_profile)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def withdraw(request):
    """Endpoint to request a wallet withdrawal (placeholder)."""
    return Response({"detail": "Withdrawal requested"})
