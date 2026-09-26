import re
from decimal import Decimal

from django import forms
from django.contrib.auth.models import Group, Permission
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory
from django.utils.text import slugify
from inventory.models import Inventory
from orders.models import Coupon
from products.models import (
    Brand,
    Product,
    ProductCategory,
    ProductTag,
    ProductVariant,
)
from products.variant_parsing import build_sku
from tienda.catalog import SIZE_ORDER

from .models import PanelSettings
from .permissions import ADMIN_PERM_SPECS

# Permisos que se ofrecen al armar un grupo/rol intermedio: los mismos que
# el panel ya usa para proteger sus propias vistas (ver `permissions.py`).
# Ofrecer cualquier otro permiso del sistema (por ejemplo los de
# django.contrib.admin) no tendria efecto util aqui y solo confundiria.
GROUP_PERMISSION_FILTER = Q()
for _app_label, _codename in ADMIN_PERM_SPECS:
    GROUP_PERMISSION_FILTER |= Q(content_type__app_label=_app_label, codename=_codename)


class COPPriceField(forms.Field):
    """Precio en pesos colombianos: el admin escribe y ve el numero con
    punto de miles ("300.000"), nunca decimales -- en COP nadie transa
    centavos, y el campo del modelo (`Product.base_price`,
    `ProductVariant.price_override`) ya guardaba puros enteros en la
    practica. El campo del modelo sigue siendo un DecimalField con
    decimales por compatibilidad; lo que cambia aqui es que el formulario
    nunca deja escribir ni mostrar esos decimales.
    """

    widget = forms.TextInput(attrs={"inputmode": "numeric", "class": "money-input", "data-money": "true"})

    def to_python(self, value):
        if value in self.empty_values:
            return None
        limpio = re.sub(r"[^\d]", "", str(value))
        if not limpio:
            return None
        return Decimal(limpio)

    def validate(self, value):
        super().validate(value)
        if value is not None and value < 0:
            raise forms.ValidationError("El precio no puede ser negativo.")

    def prepare_value(self, value):
        if value in (None, ""):
            return ""
        return f"{Decimal(value).to_integral_value():,.0f}".replace(",", ".")


class ProductAdminForm(forms.ModelForm):
    """Sin `image`: esa foto vive en la galeria (`ProductMedia`), la unica
    fuente de imagen del producto una vez aplicada la migracion
    0013_backfill_media_from_legacy_image. Antes este formulario tambien
    editaba `Product.image` por separado, lo que dejaba dos lugares
    distintos ("arriba" y "abajo" en la pantalla de edicion) para lo que el
    admin percibia como una sola foto."""

    base_price = COPPriceField(label="Precio base")

    class Meta:
        model = Product
        fields = [
            "name", "category", "brand", "description", "base_price", "discount",
            "stock", "featured", "tags",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "tags": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tags"].queryset = ProductTag.objects.filter(is_active=True)


class ProductVariantForm(forms.ModelForm):
    """Sin `sku` como campo editable: el codigo lo genera el sistema a
    partir del producto, la talla y el color (ver `build_sku`), con el
    mismo formato que ya usa el resto del catalogo (`GTG-0001-S-NEG`).
    Pedirselo al admin era un campo mas para llenar a mano, propenso a
    typos y a colisiones con SKUs ya usados; talla+color ya identifican
    la variante de forma unica dentro de un mismo producto (hay una
    restriccion de base de datos que lo garantiza), asi que el SKU no
    necesita ser una decision humana.
    """

    # No es un campo de ProductVariant: se guarda aparte, en Inventory.
    quantity_available = forms.IntegerField(label="Stock", min_value=0, required=False, initial=0)
    # Tallas fijas del catalogo (la misma lista que usa la tienda para
    # ordenar y mostrar tallas): evita que una variante quede con una talla
    # libre que despues no calce con el selector ni con la guia de tallas
    # de la PDP.
    size = forms.ChoiceField(
        label="Talla",
        choices=[("", "Selecciona una talla")] + [(size, size) for size in SIZE_ORDER],
    )
    price_override = COPPriceField(
        label="Precio propio", required=False,
    )

    class Meta:
        model = ProductVariant
        fields = ["size", "color", "price_override", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            try:
                self.fields["quantity_available"].initial = self.instance.inventory.quantity_available
            except Inventory.DoesNotExist:
                self.fields["quantity_available"].initial = 0

    def save_with_inventory(self, product):
        """Guarda la variante y su stock en la misma operacion.

        No se usa `save()` a secas porque el formset la llama con
        `commit=False`; el stock se persiste aparte, explicitamente, desde
        la vista. El SKU solo se genera para variantes nuevas: una ya
        guardada conserva el suyo aunque se le edite talla o color, para
        no invalidar un codigo que ya pudo quedar referenciado afuera
        (una etiqueta impresa, un pedido ya despachado).
        """
        es_nueva = self.instance.pk is None
        variant = self.save(commit=False)
        variant.product = product
        if es_nueva:
            variant.sku = build_sku(product.pk, variant.size, variant.color)
        variant.save()
        cantidad = self.cleaned_data.get("quantity_available")
        if cantidad is not None:
            Inventory.objects.update_or_create(variant=variant, defaults={"quantity_available": cantidad})
        return variant


class BaseProductVariantFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        combinaciones = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or form.cleaned_data.get("DELETE"):
                continue
            size = form.cleaned_data.get("size")
            color = (form.cleaned_data.get("color") or "").strip()
            if not size or not color:
                continue

            conflicto = ProductVariant.objects.filter(product=self.instance, size=size, color=color)
            if form.instance.pk:
                conflicto = conflicto.exclude(pk=form.instance.pk)
            if conflicto.exists():
                raise forms.ValidationError(
                    f"Ya existe una variante {size}/{color} para este producto.",
                )
            combinaciones.append((size, color))

        repetidas = {c for c in combinaciones if combinaciones.count(c) > 1}
        if repetidas:
            detalle = ", ".join(f"{size}/{color}" for size, color in repetidas)
            raise forms.ValidationError(f"Talla y color repetidos dentro del mismo formulario: {detalle}.")


ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    formset=BaseProductVariantFormSet,
    extra=1,
    can_delete=True,
)


class CategoryForm(forms.ModelForm):
    """Sin `description`: el campo existe en el modelo (por compatibilidad
    con datos previos) pero no lo lee ninguna plantilla de la tienda ni
    del panel; pedirlo en el alta rapida de categoria solo agregaba un
    campo sin uso visible a quien lo llena."""

    class Meta:
        model = ProductCategory
        fields = ["name"]
        labels = {"name": "Nombre"}


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ["name"]
        labels = {"name": "Nombre"}


class ProductTagForm(forms.ModelForm):
    class Meta:
        model = ProductTag
        fields = ["name", "color_token"]
        labels = {"name": "Nombre", "color_token": "Color"}
        # El texto de ayuda del modelo ("Token de color del tema admin...")
        # es una nota para quien lea el codigo, no para quien usa el
        # formulario: el propio <select> ya muestra opciones en español
        # (Acento, Dorado, Alerta), asi que repetir los nombres tecnicos
        # aqui solo confunde.
        help_texts = {"color_token": None}
        widgets = {
            "color_token": forms.Select(choices=[
                ("accent", "Acento (teal)"),
                ("gold", "Dorado"),
                ("danger", "Alerta (rojo)"),
            ]),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.slug:
            instance.slug = slugify(instance.name)
        if commit:
            instance.save()
        return instance


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code", "discount_type", "value", "min_purchase",
            "starts_at", "ends_at", "max_uses", "is_active",
        ]
        widgets = {
            "starts_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "ends_at": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["starts_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["ends_at"].input_formats = ["%Y-%m-%dT%H:%M"]

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        existe = Coupon.objects.filter(code=code)
        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise forms.ValidationError("Ya existe un cupon con este codigo.")
        return code

    def clean(self):
        cleaned_data = super().clean()
        inicio = cleaned_data.get("starts_at")
        fin = cleaned_data.get("ends_at")
        if inicio and fin and fin < inicio:
            self.add_error("ends_at", "La fecha de fin no puede ser anterior a la de inicio.")
        return cleaned_data


class GroupForm(forms.ModelForm):
    """Rol intermedio: un Grupo de Django con un subconjunto de permisos
    del panel. Asignar este grupo a un usuario staff le da acceso solo a
    las secciones cubiertas por esos permisos."""

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.filter(GROUP_PERMISSION_FILTER).select_related("content_type"),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Permisos",
    )

    class Meta:
        model = Group
        fields = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["permissions"].initial = self.instance.permissions.all()

    def save(self, commit=True):
        group = super().save(commit=commit)
        if commit:
            group.permissions.set(self.cleaned_data["permissions"])
        return group


class PanelSettingsForm(forms.ModelForm):
    class Meta:
        model = PanelSettings
        fields = ["low_stock_threshold"]
