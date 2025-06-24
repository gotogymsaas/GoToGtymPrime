<<<<<<< HEAD
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.db.models import Count, Avg, Sum
# importa tus modelos reales
from django.contrib.auth.models import User, Group
from users.models       import UserProfile
from products.models    import Product
from service.models     import Company
# from metric.models      import NetPromoterScore
# from orders.models      import Order
# from wellness.models    import HappinessIndex, PhysicalActivity


def staff_required(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(staff_required)
def auth_dashboard(request):
    """Dashboard principal GoToGym."""

    # 1. Usuarios
    user_count    = User.objects.count()
    group_count   = Group.objects.count()
    profile_count = UserProfile.objects.count()

    # 2. Satisfacción
    # nps_qs   = NetPromoterScore.objects.values("date").annotate(total=Count("id")).order_by("date")
    # nps_lbls = [e["date"].strftime("%Y-%m-%d") for e in nps_qs]
    # nps_vals = [e["total"] for e in nps_qs]
    # nps_avg  = NetPromoterScore.objects.aggregate(avg=Avg("score"))["avg"] or 0

    # # 3. Pedidos
    # orders_qs   = Order.objects.values("status").annotate(total=Count("id"))
    # orders_lbls = [e["status"] for e in orders_qs]
    # orders_vals = [e["total"]  for e in orders_qs]

    # 4. Otras cuentas
    product_count = Product.objects.count()
    company_count = Company.objects.count()

    # 5. Bienestar
    # avg_happy = HappinessIndex.objects.aggregate(avg=Avg("happiness_score"))["avg"] or 0
    # total_steps = PhysicalActivity.objects.aggregate(total=Sum("steps"))["total"] or 0

    ctx = {
        "user_count":        user_count,
        "group_count":       group_count,
        "profile_count":     profile_count,
        "product_count":     product_count,
        "company_count":     company_count,
        # "nps_labels":        nps_lbls,
        # "nps_data":          nps_vals,
        # "nps_avg":           round(nps_avg, 2),
        # "orders_labels":     orders_lbls,
        # "orders_data":       orders_vals,
        # "avg_happiness":     round(avg_happy, 2),
        # "total_physical_activity": total_steps,
    }
    return render(request, "dashboard/auth_dashboard.html", ctx)
=======
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.db.models import Count, Avg, Sum
# importa tus modelos reales
from django.contrib.auth.models import User, Group
from users.models       import UserProfile
from products.models    import Product
from service.models     import Company
# from metric.models      import NetPromoterScore
# from orders.models      import Order
# from wellness.models    import HappinessIndex, PhysicalActivity


def staff_required(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(staff_required)
def auth_dashboard(request):
    """Dashboard principal GoToGym."""

    # 1. Usuarios
    user_count    = User.objects.count()
    group_count   = Group.objects.count()
    profile_count = UserProfile.objects.count()

    # 2. Satisfacción
    # nps_qs   = NetPromoterScore.objects.values("date").annotate(total=Count("id")).order_by("date")
    # nps_lbls = [e["date"].strftime("%Y-%m-%d") for e in nps_qs]
    # nps_vals = [e["total"] for e in nps_qs]
    # nps_avg  = NetPromoterScore.objects.aggregate(avg=Avg("score"))["avg"] or 0

    # # 3. Pedidos
    # orders_qs   = Order.objects.values("status").annotate(total=Count("id"))
    # orders_lbls = [e["status"] for e in orders_qs]
    # orders_vals = [e["total"]  for e in orders_qs]

    # 4. Otras cuentas
    product_count = Product.objects.count()
    company_count = Company.objects.count()

    # 5. Bienestar
    # avg_happy = HappinessIndex.objects.aggregate(avg=Avg("happiness_score"))["avg"] or 0
    # total_steps = PhysicalActivity.objects.aggregate(total=Sum("steps"))["total"] or 0

    ctx = {
        "user_count":        user_count,
        "group_count":       group_count,
        "profile_count":     profile_count,
        "product_count":     product_count,
        "company_count":     company_count,
        # "nps_labels":        nps_lbls,
        # "nps_data":          nps_vals,
        # "nps_avg":           round(nps_avg, 2),
        # "orders_labels":     orders_lbls,
        # "orders_data":       orders_vals,
        # "avg_happiness":     round(avg_happy, 2),
        # "total_physical_activity": total_steps,
    }
    return render(request, "dashboard/auth_dashboard.html", ctx)
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
