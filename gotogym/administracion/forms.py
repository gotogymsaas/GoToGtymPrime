from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory
from inventory.models import Inventory
from products.models import Brand, Product, ProductCategory, ProductMedia, ProductVariant


class ProductAdminForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "category", "brand", "description", "base_price", "discount", "stock", "featured", "image"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ProductVariantForm(forms.ModelForm):
    # No es un campo de ProductVariant: se guarda aparte, en Inventory.
    quantity_available = forms.IntegerField(label="Stock", min_value=0, required=False, initial=0)

    class Meta:
        model = ProductVariant
        fields = ["sku", "size", "color", "price_override", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            try:
                self.fields["quantity_available"].initial = self.instance.inventory.quantity_available
            except Inventory.DoesNotExist:
                self.fields["quantity_available"].initial = 0

    def clean_sku(self):
        sku = self.cleaned_data["sku"].strip()
        existe = ProductVariant.objects.filter(sku=sku)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise forms.ValidationError("Ya existe una variante con este SKU.")
        return sku

    def save_with_inventory(self, product):
        """Guarda la variante y su stock en la misma operacion.

        No se usa `save()` a secas porque el formset la llama con
        `commit=False`; el stock se persiste aparte, explicitamente, desde
        la vista.
        """
        variant = self.save(commit=False)
        variant.product = product
        variant.save()
        cantidad = self.cleaned_data.get("quantity_available")
        if cantidad is not None:
            Inventory.objects.update_or_create(variant=variant, defaults={"quantity_available": cantidad})
        return variant


class BaseProductVariantFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        skus = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            sku = form.cleaned_data.get("sku")
            if sku:
                skus.append(sku)
        duplicados = {sku for sku in skus if skus.count(sku) > 1}
        if duplicados:
            raise forms.ValidationError(f"SKU repetido dentro del mismo formulario: {', '.join(duplicados)}.")


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    formset=BaseProductVariantFormSet,
    extra=1,
    can_delete=True,
)


class ProductMediaForm(forms.ModelForm):
    class Meta:
        model = ProductMedia
        fields = ["image", "alt_text", "sort_order", "is_primary"]


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ["name", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name"]
