from decimal import Decimal

from django.db import migrations


MARGEN_MIN = Decimal('2.5')


def subir_margen_izquierdo(apps, schema_editor):
    """Eleva PlantillaDocumento.margen_izquierdo_cm < 2.5 a 2.5.

    El sidebar de verificación (QR + código) ocupa 2.2cm fijos a la izquierda;
    necesitamos al menos 2.5cm de margen para que no invada el contenido.
    Plantillas viejas que se subieron antes de la validación quedan bajas y
    rompen el render de los nuevos PDFs.
    """
    PlantillaDocumento = apps.get_model('tramites', 'PlantillaDocumento')
    PlantillaDocumento.objects.filter(margen_izquierdo_cm__lt=MARGEN_MIN).update(
        margen_izquierdo_cm=MARGEN_MIN
    )


def revertir(apps, schema_editor):
    """No-op: no podemos saber el valor original al revertir."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('tramites', '0012_poblar_plantilla_snapshot_legado'),
    ]

    operations = [
        migrations.RunPython(subir_margen_izquierdo, revertir),
    ]
