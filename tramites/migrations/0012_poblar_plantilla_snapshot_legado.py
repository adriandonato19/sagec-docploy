from django.db import migrations


SNAPSHOT_LEGADO = {
    'imagen_header_path': 'static/img/logo_oficial.png',
    'imagen_footer_path': 'static/img/footer_certificado.png',
    'margen_superior_cm': 2.5,
    'margen_inferior_cm': 2.5,
    'margen_izquierdo_cm': 2.5,
    'margen_derecho_cm': 2.5,
}


def poblar_snapshots_legados(apps, schema_editor):
    """Pobla plantilla_snapshot en trámites ya generados para preservar diseño."""
    Tramite = apps.get_model('tramites', 'Tramite')
    Tramite.objects.filter(plantilla_snapshot={}).exclude(estado='BORRADOR').update(
        plantilla_snapshot=SNAPSHOT_LEGADO
    )


def revertir(apps, schema_editor):
    Tramite = apps.get_model('tramites', 'Tramite')
    Tramite.objects.filter(plantilla_snapshot=SNAPSHOT_LEGADO).update(plantilla_snapshot={})


class Migration(migrations.Migration):

    dependencies = [
        ('tramites', '0011_tramite_plantilla_snapshot_plantilladocumento_and_more'),
    ]

    operations = [
        migrations.RunPython(poblar_snapshots_legados, revertir),
    ]
