<<<<<<< HEAD
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.views.generic.list import ListView
from products.models import Product, Category
from .forms import ProductForm, CategoryForm


class BaseFormView(FormView):
    success_url_name = ""

    def get_success_url(self):
        return reverse_lazy(self.success_url_name)


class ProductFormView(BaseFormView):
    template_name = "products/add_product.html"
    form_class = ProductForm
    success_url_name = "products:list_product"


    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
    
    def form_invalid(self, form):
        print("Errores en el formulario:", form.errors)
        return super().form_invalid(form)



class CategoryFormView(BaseFormView):
    template_name = "products/add_category.html"
    form_class = CategoryForm
    success_url_name = "list_category"

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
    



from django.contrib.auth.mixins import UserPassesTestMixin


class ProductListView(UserPassesTestMixin, ListView):
    model = Product
    template_name = 'products/list_product.html'
    context_object_name = 'products'
    paginate_by = 4
    
    def test_func(self):
        return self.request.user.is_superuser
    
    def get_queryset(self):
        queryset = Product.objects.all().order_by('created_at')
        query = self.request.GET.get('q')
        

        categoria = self.request.GET.get('category')

        if query:
            queryset = queryset.filter(name__icontains=query)
        if categoria:
            queryset = queryset.filter(category_id=categoria)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context["categories"] = Category.objects.all()
        return context


class CategoryListView(ListView):
    model = Category
    template_name = "products/list_category.html"
=======
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.views.generic.list import ListView
from products.models import Product, Category
from .forms import ProductForm, CategoryForm


class BaseFormView(FormView):
    success_url_name = ""

    def get_success_url(self):
        return reverse_lazy(self.success_url_name)


class ProductFormView(BaseFormView):
    template_name = "products/add_product.html"
    form_class = ProductForm
    success_url_name = "products:list_product"


    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
    
    def form_invalid(self, form):
        print("Errores en el formulario:", form.errors)
        return super().form_invalid(form)



class CategoryFormView(BaseFormView):
    template_name = "products/add_category.html"
    form_class = CategoryForm
    success_url_name = "list_category"

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
    



from django.contrib.auth.mixins import UserPassesTestMixin


class ProductListView(UserPassesTestMixin, ListView):
    model = Product
    template_name = 'products/list_product.html'
    context_object_name = 'products'
    paginate_by = 4
    
    def test_func(self):
        return self.request.user.is_superuser  
    
    def get_queryset(self):
        queryset = Product.objects.all().order_by('created_at')
        query = self.request.GET.get('q')
        

        categoria = self.request.GET.get('category')

        if query:
            queryset = queryset.filter(name__icontains=query)
        if categoria:
            queryset = queryset.filter(category_id=categoria)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        context["categories"] = Category.objects.all()
        return context


class CategoryListView(ListView):
    model = Category
    template_name = "products/list_category.html"
>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
    context_object_name = "categories"