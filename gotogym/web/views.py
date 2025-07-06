from django.shortcuts import render, redirect
from .models import TemplateConfig
from .forms import TemplateConfigForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required

@login_required
def config_web(request):
    config, created = TemplateConfig.objects.get_or_create(template_name='home')
    if request.method == 'POST':
        form = TemplateConfigForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada correctamente.')
            return redirect('web:config')
    else:
        form = TemplateConfigForm(instance=config)
    return render(request, 'web/config_web.html', {'form': form, 'config': config})
