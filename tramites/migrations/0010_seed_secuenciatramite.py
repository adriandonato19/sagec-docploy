"""Sembrar SecuenciaTramite con el mayor numero_referencia ya emitido por
(tipo_documento, año), para que la nueva lógica de generación atómica
continúe la numeración existente sin saltos ni colisiones.
"""
from django.db import migrations


def sembrar_secuencias(apps, schema_editor):
    Tramite = apps.get_model('tramites', 'Tramite')
    SecuenciaTramite = apps.get_model('tramites', 'SecuenciaTramite')

    # Recorre todos los trámites y agrupa por (tipo, año) calculando el máximo.
    maximos = {}
    for tipo, fecha, ref in Tramite.objects.values_list(
        'tipo_documento', 'fecha_creacion', 'numero_referencia'
    ):
        if not ref:
            continue
        try:
            n = int(ref)
        except (TypeError, ValueError):
            continue
        clave = (tipo, fecha.year)
        if n > maximos.get(clave, 0):
            maximos[clave] = n

    for (tipo, anio), ultimo in maximos.items():
        SecuenciaTramite.objects.update_or_create(
            tipo_documento=tipo,
            anio=anio,
            defaults={'ultimo_numero': ultimo},
        )


def revertir(apps, schema_editor):
    SecuenciaTramite = apps.get_model('tramites', 'SecuenciaTramite')
    SecuenciaTramite.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('tramites', '0009_secuenciatramite'),
    ]

    operations = [
        migrations.RunPython(sembrar_secuencias, revertir),
    ]
