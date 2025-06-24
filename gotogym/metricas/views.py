<<<<<<< HEAD


import json
from django.views.generic import TemplateView
from django.db.models import Avg
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from .models import NetPromoterScore
from collections import defaultdict
from statistics import median
from django.contrib.auth.models import Group, User

from django.shortcuts import redirect




class NPSChartView(TemplateView):
    template_name = "metricas/nps_chart.html"
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_range = self.request.GET.get("range", "day")

        # Define truncation based on the selected range
        if selected_range == "month":
            trunc_func = TruncMonth
            date_format = "%Y-%m"
        elif selected_range == "year":
            trunc_func = TruncYear
            date_format = "%Y"
        else:
            trunc_func = TruncDay
            date_format = "%Y-%m-%d"

        # Obtener todos los registros y truncar la fecha según el rango seleccionado
        nps_records = NetPromoterScore.objects.annotate(
            date_trunc=trunc_func("date")
        ).order_by("date_trunc")

        # Organizar los puntajes por fecha truncada
        scores_by_date = defaultdict(list)
        for record in nps_records:
            scores_by_date[record.date_trunc].append(record.score)

        # Preparar las listas para las fechas, promedios, medianas y datos individuales
        dates = []
        avg_scores = []
        median_scores = []
        all_scores = []  # Lista de listas para los datos individuales

        for date_trunc in sorted(scores_by_date.keys()):
            scores = scores_by_date[date_trunc]
            avg = sum(scores) / len(scores)
            med = median(scores)
            dates.append(date_trunc.strftime(date_format))
            avg_scores.append(round(avg, 2))
            median_scores.append(med)
            all_scores.append(scores)  # Añadimos los puntajes individuales

        # Añadir los datos al contexto
        context["dates"] = json.dumps(dates)
        context["avg_scores"] = json.dumps(avg_scores)
        context["median_scores"] = json.dumps(median_scores)
        context["all_scores"] = json.dumps(all_scores)
        context["selected_range"] = selected_range

        return context


class GroupChartView(TemplateView):
    template_name = "metricas/grup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_range = self.request.GET.get("range", "day")

        # Definir la función de truncamiento según el rango seleccionado
        if selected_range == "month":
            trunc_func = TruncMonth
            date_format = "%Y-%m"
        elif selected_range == "year":
            trunc_func = TruncYear
            date_format = "%Y"
        else:
            trunc_func = TruncDay
            date_format = "%Y-%m-%d"

        # Obtener el grupo "Administrador"
        try:
            admin_group = Group.objects.get(name="administrador")
        except Group.DoesNotExist:
            admin_group = None

        if admin_group:
            # Obtener usuarios en el grupo "Administrador" y truncar su fecha de creación
            users_in_group = User.objects.filter(groups=admin_group).annotate(
                date_trunc=trunc_func("date_joined")
            ).order_by("date_trunc")

            # Organizar los usuarios por fecha truncada
            users_by_date = defaultdict(list)
            for user in users_in_group:
                users_by_date[user.date_trunc].append(user)

            # Preparar listas para las fechas, promedios, medianas y totales
            dates = []
            avg_users = []
            median_users = []
            total_users = []

            for date_trunc in sorted(users_by_date.keys()):
                user_counts = [1] * len(users_by_date[date_trunc])  # Cada usuario cuenta como 1
                avg = sum(user_counts) / len(user_counts)
                med = median(user_counts)
                total = sum(user_counts)

                dates.append(date_trunc.strftime(date_format))
                avg_users.append(round(avg, 2))
                median_users.append(med)
                total_users.append(total)

            # Añadir los datos al contexto
            context["dates"] = json.dumps(dates)
            context["avg_users"] = json.dumps(avg_users)
            context["median_users"] = json.dumps(median_users)
            context["total_users"] = json.dumps(total_users)
        else:
            # Si no existe el grupo "Administrador", pasar listas vacías
            context["dates"] = json.dumps([])
            context["avg_users"] = json.dumps([])
            context["median_users"] = json.dumps([])
            context["total_users"] = json.dumps([])

        context["selected_range"] = selected_range
        return context
    
def redirect_to_nps(request):
    return redirect("nps_chart")

=======


import json
from django.views.generic import TemplateView
from django.db.models import Avg
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from .models import NetPromoterScore
from collections import defaultdict
from statistics import median
from django.contrib.auth.models import Group, User

from django.shortcuts import redirect




class NPSChartView(TemplateView):
    template_name = "metricas/nps_chart.html"
    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_range = self.request.GET.get("range", "day")

        # Define truncation based on the selected range
        if selected_range == "month":
            trunc_func = TruncMonth
            date_format = "%Y-%m"
        elif selected_range == "year":
            trunc_func = TruncYear
            date_format = "%Y"
        else:
            trunc_func = TruncDay
            date_format = "%Y-%m-%d"

        # Obtener todos los registros y truncar la fecha según el rango seleccionado
        nps_records = NetPromoterScore.objects.annotate(
            date_trunc=trunc_func("date")
        ).order_by("date_trunc")

        # Organizar los puntajes por fecha truncada
        scores_by_date = defaultdict(list)
        for record in nps_records:
            scores_by_date[record.date_trunc].append(record.score)

        # Preparar las listas para las fechas, promedios, medianas y datos individuales
        dates = []
        avg_scores = []
        median_scores = []
        all_scores = []  # Lista de listas para los datos individuales

        for date_trunc in sorted(scores_by_date.keys()):
            scores = scores_by_date[date_trunc]
            avg = sum(scores) / len(scores)
            med = median(scores)
            dates.append(date_trunc.strftime(date_format))
            avg_scores.append(round(avg, 2))
            median_scores.append(med)
            all_scores.append(scores)  # Añadimos los puntajes individuales

        # Añadir los datos al contexto
        context["dates"] = json.dumps(dates)
        context["avg_scores"] = json.dumps(avg_scores)
        context["median_scores"] = json.dumps(median_scores)
        context["all_scores"] = json.dumps(all_scores)
        context["selected_range"] = selected_range

        return context


class GroupChartView(TemplateView):
    template_name = "metricas/grup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_range = self.request.GET.get("range", "day")

        # Definir la función de truncamiento según el rango seleccionado
        if selected_range == "month":
            trunc_func = TruncMonth
            date_format = "%Y-%m"
        elif selected_range == "year":
            trunc_func = TruncYear
            date_format = "%Y"
        else:
            trunc_func = TruncDay
            date_format = "%Y-%m-%d"

        # Obtener el grupo "Administrador"
        try:
            admin_group = Group.objects.get(name="administrador")
        except Group.DoesNotExist:
            admin_group = None

        if admin_group:
            # Obtener usuarios en el grupo "Administrador" y truncar su fecha de creación
            users_in_group = User.objects.filter(groups=admin_group).annotate(
                date_trunc=trunc_func("date_joined")
            ).order_by("date_trunc")

            # Organizar los usuarios por fecha truncada
            users_by_date = defaultdict(list)
            for user in users_in_group:
                users_by_date[user.date_trunc].append(user)

            # Preparar listas para las fechas, promedios, medianas y totales
            dates = []
            avg_users = []
            median_users = []
            total_users = []

            for date_trunc in sorted(users_by_date.keys()):
                user_counts = [1] * len(users_by_date[date_trunc])  # Cada usuario cuenta como 1
                avg = sum(user_counts) / len(user_counts)
                med = median(user_counts)
                total = sum(user_counts)

                dates.append(date_trunc.strftime(date_format))
                avg_users.append(round(avg, 2))
                median_users.append(med)
                total_users.append(total)

            # Añadir los datos al contexto
            context["dates"] = json.dumps(dates)
            context["avg_users"] = json.dumps(avg_users)
            context["median_users"] = json.dumps(median_users)
            context["total_users"] = json.dumps(total_users)
        else:
            # Si no existe el grupo "Administrador", pasar listas vacías
            context["dates"] = json.dumps([])
            context["avg_users"] = json.dumps([])
            context["median_users"] = json.dumps([])
            context["total_users"] = json.dumps([])

        context["selected_range"] = selected_range
        return context
    
def redirect_to_nps(request):
    return redirect("nps_chart")

>>>>>>> 0e6e1bad419e6ab057c6fb7929bf260f07e3bd01
