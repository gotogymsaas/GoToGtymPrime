<<<<<<< HEAD
from django.contrib.auth.forms import UserCreationForm
from django.views import generic
from django.urls import reverse_lazy
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from users.models import UserProfile
from django.views import View
from .forms import UserProfileForm, CustomUserCreationForm
from django.shortcuts import render, redirect
from django.contrib import messages



class RegisterView(generic.CreateView):
    form_class = UserCreationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("login")


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    fields = ["nit", "phone", "logo", "contact_name", "position", "empresa"]
    template_name = "users/userprofile_form.html"
    success_url = reverse_lazy("perfil")

    def get_object(self, queryset=None):
        user = self.request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        return profile
    

class UserProfileCreateView(LoginRequiredMixin,View):
    template_name = 'users/usersprofile_form.html'

    def get(self, request, *args, **kwargs):
        user_form = CustomUserCreationForm()
        profile_form = UserProfileForm()
        return render(request, self.template_name, {
            'user_form': user_form,
            'profile_form': profile_form
        })

    def post(self, request, *args, **kwargs):
        user_form = CustomUserCreationForm(request.POST)
        profile_form = UserProfileForm(request.POST, request.FILES)

        if user_form.is_valid() and profile_form.is_valid():
            # Crear el usuario
            user = user_form.save()

            # Asignar grupo al usuario
            group = user_form.cleaned_data['group']
            user.groups.add(group)

            # Crear el perfil asociado
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()

            messages.success(request, "El usuario, perfil y grupo se configuraron correctamente.")
            return redirect('success_url')  # Cambia 'success_url' por la URL de éxito.

        messages.error(request, "Por favor corrige los errores.")
        return render(request, self.template_name, {
            'user_form': user_form,
            'profile_form': profile_form
        })


from django.contrib.auth.views import LoginView
from django.shortcuts import redirect

class CustomLoginView(LoginView):
    template_name = 'users/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)
    def get_success_url(self):
        if self.request.user.is_superuser:
            return '../adminpanel'
        else:
            return '../'

=======
from django.contrib.auth.forms import UserCreationForm
from django.views import generic
from django.urls import reverse_lazy
from django.views.generic.edit import UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from users.models import UserProfile
from django.views import View
from .forms import UserProfileForm, CustomUserCreationForm
from django.shortcuts import render, redirect
from django.contrib import messages



class RegisterView(generic.CreateView):
    form_class = UserCreationForm
    template_name = "users/register.html"
    success_url = reverse_lazy("login")


class UserProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = UserProfile
    fields = ["nit", "phone", "logo", "contact_name", "position", "empresa"]
    template_name = "users/userprofile_form.html"
    success_url = reverse_lazy("perfil")

    def get_object(self, queryset=None):
        user = self.request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        return profile
    

class UserProfileCreateView(LoginRequiredMixin,View):
    template_name = 'users/usersprofile_form.html'

    def get(self, request, *args, **kwargs):
        user_form = CustomUserCreationForm()
        profile_form = UserProfileForm()
        return render(request, self.template_name, {
            'user_form': user_form,
            'profile_form': profile_form
        })

    def post(self, request, *args, **kwargs):
        user_form = CustomUserCreationForm(request.POST)
        profile_form = UserProfileForm(request.POST, request.FILES)

        if user_form.is_valid() and profile_form.is_valid():
            # Crear el usuario
            user = user_form.save()

            # Asignar grupo al usuario
            group = user_form.cleaned_data['group']
            user.groups.add(group)

            # Crear el perfil asociado
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()

            messages.success(request, "El usuario, perfil y grupo se configuraron correctamente.")
            return redirect('success_url')  # Cambia 'success_url' por la URL de éxito.

        messages.error(request, "Por favor corrige los errores.")
        return render(request, self.template_name, {
            'user_form': user_form,
            'profile_form': profile_form
        })



>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
