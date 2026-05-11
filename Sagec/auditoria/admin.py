from django.contrib import admin
from .models import BitacoraEvento, ConsultaSecuencia


@admin.register(ConsultaSecuencia)
class ConsultaSecuenciaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'consulta', 'resultados_encontrados', 'usuario', 'ip_origen', 'tramite', 'timestamp')
    list_filter = ('timestamp', 'usuario')
    search_fields = ('consulta', 'usuario__username')
    readonly_fields = ('numero', 'consulta', 'resultados_encontrados', 'resultados_detalle', 'timestamp', 'usuario', 'ip_origen', 'tramite')
    ordering = ('-numero',)
