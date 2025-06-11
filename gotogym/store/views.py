from django.views.generic import ListView, DetailView
from products.models import Product, Category
from django.db.models import Q, F
from cart.cart import SessionCart
from django.shortcuts import redirect

class ProductGrid(ListView):
    model = Product
    template_name = "store/list.html"
    context_object_name = "products"
    paginate_by = 6
    
    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        cat = self.request.GET.get("cat")
        if cat:
            qs=qs.filter(category_id=cat)
        price_min= self.request.GET.get("min")
        price_max= self.request.GET.get("max")
        
        if price_min:
            qs = qs.filter(price__gte=price_min)
        if price_max:
            qs = qs.filter(price__lte=price_max)
        order = self.request.GET.get("o")
        ordering = {
            "a":  "name",
            "za": "-name",
            "p":  "price",
            "mp": "-price",
        }.get(order)
        if ordering:
            qs = qs.order_by(ordering)

        return qs.select_related("category")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["cats"] = Category.objects.all()
        ctx["params"] = self.request.GET.copy()
        if "page" in ctx["params"]:
            del ctx["params"]["page"]
        return ctx

class ProductDetail(DetailView):
    model = Product
    template_name = "store/detail.html"
    context_object_name = "product"


    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        qty = int(request.POST.get("qty", 1))
        SessionCart(request).add(self.object.id, qty)
        return redirect("cart/detail.html")
