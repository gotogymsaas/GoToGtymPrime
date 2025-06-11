from django.contrib import admin
from .models import UserProfile


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "empresa", "phone","logo",'user_group')
    search_fields = ("user__username", "empresa", "phone")
    list_filter = ("empresa",)

    def user_group(self, obj):
        return " - ".join([t.name for t in obj.user.groups.all().order_by('name')])

    user_group.short_description = 'Grupo'

admin.site.register(UserProfile, UserProfileAdmin)
