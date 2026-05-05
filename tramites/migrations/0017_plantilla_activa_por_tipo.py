from django.db import migrations, models


def forward(apps, schema_editor):
    PlantillaDocumento = apps.get_model('tramites', 'PlantillaDocumento')
    for p in PlantillaDocumento.objects.filter(activa=True):
        if p.tipo_aplicable in ('CERTIFICADO', 'AMBOS'):
            p.activa_certificado = True
        if p.tipo_aplicable in ('OFICIO', 'AMBOS'):
            p.activa_oficio = True
        p.save(update_fields=['activa_certificado', 'activa_oficio'])


def backward(apps, schema_editor):
    PlantillaDocumento = apps.get_model('tramites', 'PlantillaDocumento')
    for p in PlantillaDocumento.objects.filter(
        activa_certificado=True
    ) | PlantillaDocumento.objects.filter(activa_oficio=True):
        p.activa = True
        p.save(update_fields=['activa'])


class Migration(migrations.Migration):

    dependencies = [
        ('tramites', '0016_add_cuerpo_plantilla_html'),
    ]

    operations = [
        migrations.AddField(
            model_name='plantilladocumento',
            name='activa_certificado',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='plantilladocumento',
            name='activa_oficio',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(forward, backward),
        migrations.RemoveConstraint(
            model_name='plantilladocumento',
            name='una_plantilla_activa_por_tipo',
        ),
        migrations.RemoveField(
            model_name='plantilladocumento',
            name='activa',
        ),
    ]
