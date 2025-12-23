from django.contrib import admin
from .models import  Member, Cycle, Group


# Register your models here.
admin.site.register(Group)
admin.site.register(Member)
admin.site.register(Cycle)


