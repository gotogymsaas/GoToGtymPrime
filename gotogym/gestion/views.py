from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView

class ViewView(LoginRequiredMixin, View):
    template_name = "gestion/index.html"

    def get(self, request, *args, **kwargs):
        # Puedes pasar datos al contexto si es necesario
        context = {
            "message": "¡Hola, este es un ejemplo de vista basada en clases!",
        }
        return render(request, self.template_name, context)
    
class RoleBasedRedirectView(LoginRequiredMixin, View):
    admin_view_name = "admin_view"  # Nombre de la vista para administradores
    default_view_name = "user_view"  # Nombre de la vista para usuarios no administradores

    def get(self, request, *args, **kwargs):
        # Verifica si el usuario pertenece al grupo "Administrador"
        if request.user.groups.filter(name="administrador").exists():
            return redirect(self.admin_view_name)
        # Si no pertenece, renderiza otra vista
        return redirect(self.default_view_name)
        
class AdminView(TemplateView):
    template_name = "gestion/home_view.html"
    
class UserView(TemplateView):
    template_name = "gestion/user_view.html"

class HomeView(TemplateView):
    template_name="gestion/index.html"

class TallaView(TemplateView):
    template_name = "gestion/talla.html"

class BlogView(TemplateView):
    template_name = "gestion/blog.html"