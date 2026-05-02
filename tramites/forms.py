"""Formularios de la app de trámites."""
from django import forms

from .models import PlantillaDocumento


class PlantillaDocumentoSubirForm(forms.ModelForm):
    """Form de subida de plantilla. Solo nombre, tipo y archivo Word.

    Las imágenes y márgenes se rellenan automáticamente al procesar el .docx
    en la vista (ver `subir_plantilla_view`).
    """

    archivo_word = forms.FileField(
        label='Archivo Word (.docx)',
        widget=forms.ClearableFileInput(attrs={'accept': '.docx'}),
    )

    class Meta:
        model = PlantillaDocumento
        fields = ['nombre', 'tipo_aplicable', 'archivo_word']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'w-full'}),
            'tipo_aplicable': forms.RadioSelect(),
        }


class PlantillaDocumentoMargenesForm(forms.ModelForm):
    """Form de ajuste de márgenes desde la pantalla de detalle."""

    # El sidebar de QR + código de verificación ocupa 2.2cm fijos a la izquierda;
    # se necesita al menos 0.3cm de gap para que no invada el contenido.
    MARGEN_IZQUIERDO_MIN = 2.5

    class Meta:
        model = PlantillaDocumento
        fields = [
            'margen_superior_cm',
            'margen_inferior_cm',
            'margen_izquierdo_cm',
            'margen_derecho_cm',
        ]
        widgets = {
            'margen_superior_cm': forms.NumberInput(attrs={'step': '0.1', 'min': '0.5', 'max': '5.0'}),
            'margen_inferior_cm': forms.NumberInput(attrs={'step': '0.1', 'min': '0.5', 'max': '5.0'}),
            'margen_izquierdo_cm': forms.NumberInput(attrs={'step': '0.1', 'min': '2.5', 'max': '5.0'}),
            'margen_derecho_cm': forms.NumberInput(attrs={'step': '0.1', 'min': '0.5', 'max': '5.0'}),
        }

    def clean_margen_izquierdo_cm(self):
        valor = self.cleaned_data['margen_izquierdo_cm']
        if valor < self.MARGEN_IZQUIERDO_MIN:
            raise forms.ValidationError(
                f'El margen izquierdo debe ser al menos {self.MARGEN_IZQUIERDO_MIN} cm '
                'para que el sidebar de verificación (QR + código) no invada el contenido.'
            )
        return valor
