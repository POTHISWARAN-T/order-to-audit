from django.contrib import admin
from .models import Item, BOM, BOMLine, Customer, Supplier

class BOMLineInline(admin.TabularInline):
    model = BOMLine

@admin.register(BOM)
class BOMAdmin(admin.ModelAdmin):
    inlines = [BOMLineInline]

admin.site.register([Item, Customer, Supplier])