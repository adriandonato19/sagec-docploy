from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.utils import timezone
from django.conf import settings
from pathlib import Path
import os
import json
from .models import Tramite, PreguntaOficio, SecuenciaTramite, PlantillaDocumento
from .forms import PlantillaDocumentoSubirForm, PlantillaDocumentoMargenesForm
from .services.generador_pdf import generar_pdf_tramite, generar_html_tramite, generar_pdf_desde_html, calcular_hash_pdf, extraer_contenido_editable, reinyectar_contenido_editado
from .services.extractor_plantilla import extraer_plantilla_desde_docx
from .services.firma_digital import certificado_disponible, firmar_pdf_con_certificado
from .services.notificaciones import enviar_notificacion_firma
from identidad.decorators import require_rol
from identidad.models import UsuarioMICI
from integracion.services import (
    buscar_empresa_por_campo,
    buscar_empresa_todas_paginas,
    campo_busqueda_valido,
    construir_noconsta_entry,
    es_misma_entrada_noconsta,
    normalizar_noconsta_entries,
)
from integracion.adapters import normalizar_datos_empresa, construir_ubicacion_completa
from auditoria.services import registrar_evento, obtener_ip_cliente
from auditoria.models import BitacoraEvento, ConsultaSecuencia


def _normalizar_noconsta_en_sesion(request):
    """Normaliza el carrito de No Consta y preserva compatibilidad con sesiones legadas."""
    noconsta_cart = normalizar_noconsta_entries(request.session.get('noconsta_cart', []))
    if request.session.get('noconsta_cart', []) != noconsta_cart:
        request.session['noconsta_cart'] = noconsta_cart
    return noconsta_cart


def _agregar_empresas_por_ruc(request, ruc: str):
    """Agrega al carrito todos los avisos asociados al RUC recibido."""
    ruc = str(ruc or '').strip()
    if not ruc:
        return HttpResponse('<div class="p-2 text-red-600 text-sm">Debe ingresar un RUC.</div>', status=400)

    resultados_raw = buscar_empresa_todas_paginas(ruc)
    if not resultados_raw:
        return HttpResponse('<div class="p-2 text-red-600 text-sm">No se encontró empresa con ese RUC.</div>', status=404)

    empresas_cart = request.session.get('empresas_cart', [])

    nuevas_empresas = []
    for raw in resultados_raw:
        emp = normalizar_datos_empresa(raw)
        emp['ubicacion_completa'] = construir_ubicacion_completa(emp)
        nuevas_empresas.append(emp)

    avisos_en_cart = {e.get('numero_aviso') for e in empresas_cart}
    agregados = 0
    for emp in nuevas_empresas:
        if emp.get('numero_aviso') not in avisos_en_cart:
            empresas_cart.append(emp)
            avisos_en_cart.add(emp.get('numero_aviso'))
            agregados += 1

    if agregados == 0:
        return HttpResponse('<div class="p-2 text-yellow-600 text-sm">Todos los avisos de este RUC ya fueron agregados.</div>', status=400)

    request.session['empresas_cart'] = empresas_cart

    response = render(request, 'tramites/partials/lista_empresas_cart.html', {
        'empresas_cart': empresas_cart,
    })
    response['HX-Trigger'] = 'empresas-changed'
    return response


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
def bandeja_admin_view(request):
    """
    Bandeja de administración con tabs por estado.
    Filtros y paginación server-side con HTMX.
    """
    estado_filtro = request.GET.get('estado', '')
    busqueda = request.GET.get('q', '').strip()
    page = request.GET.get('page', 1)
    
    # Base queryset: todos los trámites
    queryset = Tramite.objects.all()
    
    # Filtro por estado
    if estado_filtro and estado_filtro != 'TODOS':
        queryset = queryset.filter(estado=estado_filtro)
    
    # Búsqueda
    if busqueda:
        queryset = queryset.filter(
            Q(numero_referencia__icontains=busqueda) |
            Q(origen_consulta__icontains=busqueda) |
            Q(solicitante__username__icontains=busqueda) |
            Q(solicitante__first_name__icontains=busqueda) |
            Q(solicitante__last_name__icontains=busqueda)
        )
    
    # Contadores por estado
    contadores = {
        'TODOS': Tramite.objects.count(),
        Tramite.BORRADOR: Tramite.objects.filter(estado=Tramite.BORRADOR).count(),
        Tramite.PENDIENTE: Tramite.objects.filter(estado=Tramite.PENDIENTE).count(),
        Tramite.EN_REVISION: Tramite.objects.filter(estado=Tramite.EN_REVISION).count(),
        Tramite.APROBADO: Tramite.objects.filter(estado=Tramite.APROBADO).count(),
        Tramite.FIRMADO: Tramite.objects.filter(estado=Tramite.FIRMADO).count(),
        Tramite.RECHAZADO: Tramite.objects.filter(estado=Tramite.RECHAZADO).count(),
    }
    
    # Paginación
    paginator = Paginator(queryset, 10)
    tramites = paginator.get_page(page)
    
    # Tabs para la UI
    tabs = [
        {'label': 'Todos', 'url': '?estado=', 'count': contadores['TODOS'], 'active': not estado_filtro or estado_filtro == 'TODOS'},
        {'label': 'Pendientes', 'url': f'?estado={Tramite.PENDIENTE}', 'count': contadores[Tramite.PENDIENTE], 'active': estado_filtro == Tramite.PENDIENTE},
        {'label': 'En revisión', 'url': f'?estado={Tramite.EN_REVISION}', 'count': contadores[Tramite.EN_REVISION], 'active': estado_filtro == Tramite.EN_REVISION},
        {'label': 'Aprobados', 'url': f'?estado={Tramite.APROBADO}', 'count': contadores[Tramite.APROBADO], 'active': estado_filtro == Tramite.APROBADO},
        {'label': 'Firmados', 'url': f'?estado={Tramite.FIRMADO}', 'count': contadores[Tramite.FIRMADO], 'active': estado_filtro == Tramite.FIRMADO},
        {'label': 'Rechazados', 'url': f'?estado={Tramite.RECHAZADO}', 'count': contadores[Tramite.RECHAZADO], 'active': estado_filtro == Tramite.RECHAZADO},
    ]
    
    context = {
        'tramites': tramites,
        'tabs': tabs,
        'estado_filtro': estado_filtro,
        'busqueda': busqueda,
        'contadores': contadores,
    }
    
    # Si es petición HTMX, devolver solo la tabla
    if request.headers.get('HX-Request'):
        return render(request, 'tramites/partials/tabla_tramites.html', context)
    
    return render(request, 'tramites/bandeja_admin.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def crear_tramite_view(request):
    """Página unificada para crear trámites (certificados y oficios)."""
    if request.method == 'POST':
        tipo_documento = request.POST.get('tipo_documento', 'CERTIFICADO')
        destinatario = request.POST.get('destinatario', '').strip()
        proposito = request.POST.get('proposito', '').strip()
        objetivo_solicitud = request.POST.get('objetivo_solicitud', '').strip()
        fecha_solicitud_str = request.POST.get('fecha_solicitud', '').strip()
        numero_carpetilla = request.POST.get('numero_carpetilla', '').strip()
        numero_oficio_externo = request.POST.get('numero_oficio_externo', '').strip()
        titulo_destinatario = request.POST.get('titulo_destinatario', '').strip()
        cargo_destinatario = request.POST.get('cargo_destinatario', '').strip()
        institucion_destinatario = request.POST.get('institucion_destinatario', '').strip()

        # Empresas y entradas No Consta del carrito en sesión
        empresas_cart = request.session.get('empresas_cart', [])
        noconsta_cart = _normalizar_noconsta_en_sesion(request)

        # Oficios requieren carpetilla y oficio externo
        if tipo_documento == 'OFICIO':
            if not numero_carpetilla:
                messages.error(request, 'El número de carpetilla es obligatorio para oficios.')
                return redirect('consultar_tramite')
            if not numero_oficio_externo:
                messages.error(request, 'El número de oficio externo es obligatorio para oficios.')
                return redirect('consultar_tramite')

        # Preguntas: filtrar vacías, permitir lista vacía
        preguntas_textos = [t.strip() for t in request.POST.getlist('preguntas[]') if t.strip()]

        empresa_snapshot = empresas_cart  # siempre lista
        origen_consulta = ', '.join(e.get('ruc_completo', e.get('ruc', '')) for e in empresas_cart)

        # Parsear fecha de solicitud
        fecha_solicitud = None
        if fecha_solicitud_str:
            try:
                from datetime import datetime
                fecha_solicitud = datetime.strptime(fecha_solicitud_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        # Crear trámite (sin generar PDF)
        tramite = Tramite.objects.create(
            tipo_documento=tipo_documento,
            solicitante=request.user,
            empresa_snapshot=empresa_snapshot,
            noconsta_snapshot=noconsta_cart,
            origen_consulta=origen_consulta,
            numero_referencia=Tramite.siguiente_numero_referencia(tipo_documento),
            estado=Tramite.BORRADOR,
            destinatario=destinatario,
            proposito=proposito,
            objetivo_solicitud=objetivo_solicitud,
            fecha_solicitud=fecha_solicitud,
            numero_carpetilla=numero_carpetilla,
            numero_oficio_externo=numero_oficio_externo,
            titulo_destinatario=titulo_destinatario,
            cargo_destinatario=cargo_destinatario,
            institucion_destinatario=institucion_destinatario,
        )

        # Guardar preguntas
        for i, texto in enumerate(preguntas_textos):
            PreguntaOficio.objects.create(
                tramite=tramite,
                orden=i,
                texto_pregunta=texto,
            )

        # Vincular consultas secuenciales al trámite
        consultas_ids = request.session.pop('consultas_secuencia_ids', [])
        if consultas_ids:
            ConsultaSecuencia.objects.filter(numero__in=consultas_ids).update(tramite=tramite)

        # Limpiar carrito de sesión
        request.session.pop('empresas_cart', None)
        request.session.pop('noconsta_cart', None)
        request.session.pop('consulta_no_consta', None)

        # Registrar evento de creación
        ip_cliente = obtener_ip_cliente(request)
        registrar_evento(
            tipo_evento=BitacoraEvento.CREACION_TRAMITE,
            actor=request.user,
            ip_origen=ip_cliente,
            recurso=tramite,
            descripcion=f'Creación de {tramite.get_tipo_documento_display()} - {origen_consulta or "sin empresa"}',
            metadata={'tipo_documento': tipo_documento, 'origen': origen_consulta}
        )

        messages.success(request, 'Trámite creado correctamente.')
        return redirect('tramites:detalle', id=tramite.uuid)

    # GET: limpiar carrito y consultas secuenciales, mostrar selector de tipo
    request.session.pop('empresas_cart', None)
    request.session.pop('noconsta_cart', None)
    request.session.pop('consultas_secuencia_ids', None)
    return render(request, 'tramites/consultar.html')


@login_required
@require_http_methods(["GET"])
def formulario_tipo_hx(request):
    """Retorna el formulario parcial según tipo de documento (HTMX)."""
    tipo_documento = request.GET.get('tipo', 'CERTIFICADO')
    if tipo_documento not in ('CERTIFICADO', 'OFICIO'):
        tipo_documento = 'CERTIFICADO'

    tipo_labels = {'CERTIFICADO': 'Certificado', 'OFICIO': 'Oficio'}
    empresas_cart = request.session.get('empresas_cart', [])
    noconsta_cart = _normalizar_noconsta_en_sesion(request)

    return render(request, 'tramites/partials/formulario_tipo.html', {
        'tipo_documento': tipo_documento,
        'tipo_label': tipo_labels[tipo_documento],
        'empresas_cart': empresas_cart,
        'noconsta_cart': noconsta_cart,
        'today': timezone.now().strftime('%Y-%m-%d'),
    })


@login_required
def mis_certificados_view(request):
    """Lista de certificados del usuario actual."""
    certificados = Tramite.objects.filter(
        solicitante=request.user,
        tipo_documento='CERTIFICADO'
    ).order_by('-fecha_creacion')
    
    return render(request, 'tramites/mis_certificados.html', {
        'certificados': certificados
    })


@login_required
def mis_oficios_view(request):
    """Lista de oficios del usuario actual."""
    oficios = Tramite.objects.filter(
        solicitante=request.user,
        tipo_documento='OFICIO'
    ).order_by('-fecha_creacion')
    
    return render(request, 'tramites/mis_oficios.html', {
        'oficios': oficios
    })


@login_required
@require_http_methods(["GET", "POST"])
def detalle_view(request, id):
    """Vista de detalle de un trámite."""
    tramite = get_object_or_404(Tramite, uuid=id)
    
    # Verificar permisos: solo el solicitante, revisor o firmante pueden ver
    puede_ver = (
        tramite.solicitante == request.user or
        tramite.revisor == request.user or
        tramite.firmante == request.user or
        request.user.puede_aprobar
    )
    
    if not puede_ver:
        messages.error(request, 'No tiene permisos para ver este trámite.')
        raise Http404
    
    # Manejar POST (enviar trámite)
    if request.method == 'POST' and request.POST.get('accion') == 'enviar':
        if tramite.estado == Tramite.BORRADOR and tramite.solicitante == request.user:
            try:
                estado_anterior = tramite.estado
                tramite.enviar()
                
                # Registrar cambio de estado
                ip_cliente = obtener_ip_cliente(request)
                registrar_evento(
                    tipo_evento=BitacoraEvento.CAMBIO_ESTADO,
                    actor=request.user,
                    ip_origen=ip_cliente,
                    recurso=tramite,
                    descripcion=f'Cambio de estado: {estado_anterior} -> {tramite.estado}',
                    metadata={'estado_anterior': estado_anterior, 'estado_nuevo': tramite.estado}
                )
                
                messages.success(request, 'Trámite enviado para revisión correctamente.')
            except Exception as e:
                messages.error(request, str(e))
        else:
            messages.error(request, 'No puede enviar este trámite.')
        return redirect('tramites:detalle', id=tramite.uuid)
    
    # Contexto de preguntas
    preguntas = tramite.preguntas.all()
    todas_respondidas = all(p.esta_respondida for p in preguntas) if preguntas else True

    return render(request, 'tramites/detalle.html', {
        'tramite': tramite,
        'noconsta_entries': normalizar_noconsta_entries(tramite.noconsta_snapshot),
        'preguntas': preguntas,
        'todas_respondidas': todas_respondidas,
    })


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
@require_http_methods(["POST"])
def aprobar_view(request, id):
    """Aprobar un trámite pendiente."""
    tramite = get_object_or_404(Tramite, uuid=id)
    
    if tramite.estado != Tramite.PENDIENTE:
        messages.error(request, f'El trámite no está en estado pendiente.')
        return redirect('tramites:detalle', id=tramite.uuid)
    
    try:
        estado_anterior = tramite.estado
        tramite.aprobar(request.user)
        
        # Registrar evento de aprobación
        ip_cliente = obtener_ip_cliente(request)
        registrar_evento(
            tipo_evento=BitacoraEvento.APROBACION,
            actor=request.user,
            ip_origen=ip_cliente,
            recurso=tramite,
            descripcion=f'Aprobación de trámite - Estado anterior: {estado_anterior}',
            metadata={'estado_anterior': estado_anterior, 'revisor': request.user.username, 'fase': 'solicitud'}
        )
        
        # Guardar HTML renderizado para posible edición posterior
        if not tramite.html_pdf_editado:
            tramite.html_pdf_editado = generar_html_tramite(tramite)
            tramite.save(update_fields=['html_pdf_editado'])

        # Generar PDF al aprobar
        pdf_bytesio = generar_pdf_tramite(tramite)
        pdf_content = pdf_bytesio.read()

        pdf_filename = f'tramite_{tramite.uuid}.pdf'
        tramite.archivo_pdf.save(pdf_filename, ContentFile(pdf_content), save=True)

        messages.success(request, 'Solicitud aprobada. Revise y apruebe el PDF antes de enviarlo a firma.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('tramites:detalle', id=tramite.uuid)


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
@require_http_methods(["POST"])
def aprobar_pdf_view(request, id):
    """Aprobar el PDF final de un trámite en revisión."""
    tramite = get_object_or_404(Tramite, uuid=id)

    if tramite.estado != Tramite.EN_REVISION:
        messages.error(request, 'El trámite no está en revisión.')
        return redirect('tramites:detalle', id=tramite.uuid)

    try:
        estado_anterior = tramite.estado
        tramite.aprobar_pdf(request.user)

        ip_cliente = obtener_ip_cliente(request)
        registrar_evento(
            tipo_evento=BitacoraEvento.APROBACION,
            actor=request.user,
            ip_origen=ip_cliente,
            recurso=tramite,
            descripcion=f'Aprobación del PDF - Estado anterior: {estado_anterior}',
            metadata={'estado_anterior': estado_anterior, 'revisor': request.user.username, 'fase': 'pdf'}
        )

        messages.success(request, 'PDF aprobado correctamente. El trámite quedó aprobado.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('tramites:detalle', id=tramite.uuid)


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
@require_http_methods(["POST"])
def rechazar_view(request, id):
    """Rechazar un trámite pendiente con motivo obligatorio."""
    tramite = get_object_or_404(Tramite, uuid=id)
    motivo = request.POST.get('motivo_rechazo', '').strip()

    if tramite.estado != Tramite.PENDIENTE:
        messages.error(request, 'Solo se pueden rechazar trámites pendientes.')
        return redirect('tramites:detalle', id=tramite.uuid)

    try:
        estado_anterior = tramite.estado
        tramite.rechazar(request.user, motivo)

        ip_cliente = obtener_ip_cliente(request)
        registrar_evento(
            tipo_evento=BitacoraEvento.RECHAZO,
            actor=request.user,
            ip_origen=ip_cliente,
            recurso=tramite,
            descripcion=f'Rechazo de trámite - Estado anterior: {estado_anterior}',
            metadata={'estado_anterior': estado_anterior, 'revisor': request.user.username, 'motivo_rechazo': motivo}
        )

        messages.success(request, 'Solicitud rechazada correctamente.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('tramites:detalle', id=tramite.uuid)


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
@require_http_methods(["POST"])
def regresar_view(request, id):
    """Regresar un trámite al estado anterior del flujo."""
    tramite = get_object_or_404(Tramite, uuid=id)
    nota_regreso = request.POST.get('nota_regreso', '').strip()

    try:
        estado_anterior = tramite.estado
        tramite.regresar(request.user)

        ip_cliente = obtener_ip_cliente(request)
        registrar_evento(
            tipo_evento=BitacoraEvento.CAMBIO_ESTADO,
            actor=request.user,
            ip_origen=ip_cliente,
            recurso=tramite,
            descripcion=f'Regreso de trámite - Estado anterior: {estado_anterior}',
            metadata={
                'estado_anterior': estado_anterior,
                'estado_nuevo': tramite.estado,
                'revisor': request.user.username,
                'nota_regreso': nota_regreso,
                'accion': 'regresar',
            }
        )

        messages.success(request, f'Trámite regresado correctamente a {tramite.get_estado_display().lower()}.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('tramites:detalle', id=tramite.uuid)


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(["GET", "POST"])
def firmar_view(request, id):
    """Firmar un trámite aprobado usando certificado digital .p12 del servidor."""
    tramite = get_object_or_404(Tramite, uuid=id)

    if tramite.estado != Tramite.APROBADO:
        messages.error(request, 'El trámite debe estar aprobado para poder firmarlo.')
        return redirect('tramites:detalle', id=tramite.uuid)

    if request.method == 'POST':
        try:
            # Verificar disponibilidad del certificado
            if not certificado_disponible():
                messages.error(request, 'El certificado digital no está configurado en el servidor.')
                return render(request, 'tramites/firmar.html', {'tramite': tramite})

            estado_anterior = tramite.estado

            # Leer PDF aprobado desde storage
            if not tramite.archivo_pdf or not tramite.archivo_pdf.storage.exists(tramite.archivo_pdf.name):
                messages.error(request, 'No se encontró el PDF aprobado.')
                return render(request, 'tramites/firmar.html', {'tramite': tramite})

            with tramite.archivo_pdf.open('rb') as f:
                pdf_bytes = f.read()

            # Firmar el PDF con el certificado .p12
            pdf_firmado = firmar_pdf_con_certificado(pdf_bytes)

            # Calcular hash SHA-256 del PDF firmado
            hash_documento = calcular_hash_pdf(pdf_firmado)

            # Guardar PDF firmado en storage
            pdf_filename = f'tramite_{tramite.uuid}_firmado.pdf'
            tramite.archivo_pdf_firmado.save(pdf_filename, ContentFile(pdf_firmado), save=False)
            tramite.marcar_firmado(request.user, hash_documento=hash_documento)

            # Registrar evento de firma
            ip_cliente = obtener_ip_cliente(request)
            registrar_evento(
                tipo_evento=BitacoraEvento.FIRMA,
                actor=request.user,
                ip_origen=ip_cliente,
                recurso=tramite,
                descripcion=f'Firma de documento - Estado anterior: {estado_anterior}',
                metadata={'estado_anterior': estado_anterior, 'hash': hash_documento, 'archivo': pdf_filename, 'metodo': 'certificado_p12'}
            )

            messages.success(request, 'Documento firmado digitalmente con éxito.')
            enviar_notificacion_firma(tramite)
            return redirect('tramites:detalle', id=tramite.uuid)
        except Exception as e:
            messages.error(request, f'Error al firmar el documento: {str(e)}')

    return render(request, 'tramites/firmar.html', {
        'tramite': tramite
    })


@login_required
@xframe_options_sameorigin
def descargar_view(request, id):
    """Descargar el PDF de un trámite firmado."""
    tramite = get_object_or_404(Tramite, uuid=id)
    
    # Verificar permisos
    puede_ver = (
        tramite.solicitante == request.user or
        tramite.revisor == request.user or
        tramite.firmante == request.user or
        request.user.puede_aprobar
    )
    
    if not puede_ver:
        messages.error(request, 'No tiene permisos para descargar este documento.')
        raise Http404
    
    # Permitir descarga si el PDF existe (se genera al crear el trámite)
    if not tramite.archivo_pdf or not tramite.archivo_pdf.name:
        messages.error(request, 'El PDF aún no está disponible.')
        return redirect('tramites:detalle', id=tramite.uuid)
    
    # Determinar qué PDF servir: firmado si existe, sino regenerar desde HTML
    try:
        pdf_content = None
        pdf_filename = f'tramite_{tramite.uuid}.pdf'

        # Prioridad 1: PDF firmado si existe y el trámite está firmado
        if (tramite.estado == Tramite.FIRMADO
                and tramite.archivo_pdf_firmado
                and tramite.archivo_pdf_firmado.name
                and tramite.archivo_pdf_firmado.storage.exists(tramite.archivo_pdf_firmado.name)):
            with tramite.archivo_pdf_firmado.open('rb') as f:
                pdf_content = f.read()
            pdf_filename = f'tramite_{tramite.uuid}_firmado.pdf'

        # Prioridad 2: Regenerar PDF desde html_pdf_editado o plantilla
        if not pdf_content:
            pdf_bytesio = generar_pdf_tramite(tramite)
            pdf_content = pdf_bytesio.read()

            # Persistir en storage para la próxima descarga
            if not tramite.archivo_pdf or not tramite.archivo_pdf.name:
                tramite.archivo_pdf.save(pdf_filename, ContentFile(pdf_content), save=True)
            else:
                tramite.archivo_pdf.save(pdf_filename, ContentFile(pdf_content), save=False)
                tramite.save(update_fields=['archivo_pdf'])
        
        # Registrar evento de descarga
        ip_cliente = obtener_ip_cliente(request)
        registrar_evento(
            tipo_evento=BitacoraEvento.DESCARGA,
            actor=request.user,
            ip_origen=ip_cliente,
            recurso=tramite,
            descripcion=f'Descarga de PDF del trámite {tramite.numero_referencia or tramite.uuid}',
            metadata={'hash': tramite.hash_seguridad or 'N/A', 'tipo': 'firmado' if tramite.estado == Tramite.FIRMADO and tramite.archivo_pdf_firmado else 'original'}
        )
        
        # Determinar si es inline (vista previa) o attachment (descarga)
        inline = request.GET.get('inline', '0') == '1'
        content_disposition = 'inline' if inline else 'attachment'
        
        # Servir el PDF (sin cache para que siempre sirva la versión actual)
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'{content_disposition}; filename="{pdf_filename}"'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    except Exception as e:
        messages.error(request, f'Error al generar el PDF: {str(e)}')
        return redirect('tramites:detalle', id=tramite.uuid)


@login_required
def vista_previa_pdf_hx(request, id):
    """Vista previa del PDF en un modal (HTMX)."""
    tramite = get_object_or_404(Tramite, uuid=id)
    
    # Verificar permisos
    puede_ver = (
        tramite.solicitante == request.user or
        tramite.revisor == request.user or
        tramite.firmante == request.user or
        request.user.puede_aprobar
    )
    
    if not puede_ver:
        return HttpResponse('<div class="p-4 text-red-600">No tiene permisos para ver este documento.</div>', status=403)
    
    # Verificar que exista algún PDF (original o firmado)
    tiene_pdf = (
        (tramite.archivo_pdf and tramite.archivo_pdf.name) or 
        (tramite.archivo_pdf_firmado and tramite.archivo_pdf_firmado.name)
    )
    
    if not tiene_pdf:
        return HttpResponse('<div class="p-4 text-yellow-600">El PDF aún no está disponible. Por favor, intente más tarde.</div>', status=400)
    
    return render(request, 'tramites/partials/modal_vista_previa_pdf.html', {
        'tramite': tramite
    })


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
@require_http_methods(["POST"])
def responder_preguntas_hx(request, id):
    """Guardar respuestas a preguntas de un oficio (HTMX)."""
    tramite = get_object_or_404(Tramite, uuid=id)

    if tramite.estado != Tramite.PENDIENTE:
        return HttpResponse('<div class="p-4 text-red-600">El trámite no está en estado pendiente.</div>', status=400)

    preguntas = tramite.preguntas.all()
    for pregunta in preguntas:
        respuesta = request.POST.get(f'respuesta_{pregunta.id}', '').strip()
        if respuesta:
            pregunta.texto_respuesta = respuesta
            pregunta.respondida_por = request.user
            pregunta.fecha_respuesta = timezone.now()
            pregunta.save()

    preguntas = tramite.preguntas.all()
    todas_respondidas = all(p.esta_respondida for p in preguntas)

    return render(request, 'tramites/partials/preguntas_detalle.html', {
        'tramite': tramite,
        'preguntas': preguntas,
        'todas_respondidas': todas_respondidas,
    })


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
@require_http_methods(["POST"])
def responder_solicitud_hx(request, id):
    """Guardar respuesta de solicitud (HTMX)."""
    tramite = get_object_or_404(Tramite, uuid=id)

    if tramite.estado != Tramite.PENDIENTE:
        return HttpResponse('<div class="p-4 text-red-600">El trámite no está en estado pendiente.</div>', status=400)

    tramite.respuesta_solicitud = request.POST.get('respuesta_solicitud', '').strip()
    tramite.save(update_fields=['respuesta_solicitud'])

    preguntas = tramite.preguntas.all()
    todas_respondidas = all(p.esta_respondida for p in preguntas) if preguntas else True

    return render(request, 'tramites/partials/respuesta_solicitud_detalle.html', {
        'tramite': tramite,
        'preguntas': preguntas,
        'todas_respondidas': todas_respondidas,
    })


@login_required
@require_http_methods(["POST"])
def agregar_empresa_hx(request):
    """Agregar empresa por RUC o generar No Consta automático si no hay resultados."""
    campo_busqueda = campo_busqueda_valido(request.POST.get('campo_busqueda', 'ruc'))
    query = (
        request.POST.get('ruc_empresa', '') or request.POST.get('empresa_query', '')
    ).strip()
    ruc = "-".join(query.split("-")[:3])

    if not query:
        return HttpResponse('<div class="p-2 text-red-600 text-sm">Debe ingresar un valor de búsqueda.</div>', status=400)

    resultado_busqueda = buscar_empresa_por_campo(query, campo_busqueda, page=1)
    if not resultado_busqueda:
        noconsta_entry = construir_noconsta_entry(campo_busqueda, query)
        noconsta_cart = _normalizar_noconsta_en_sesion(request)

        if any(es_misma_entrada_noconsta(actual, noconsta_entry) for actual in noconsta_cart):
            return HttpResponse(
                '<div class="p-2 text-yellow-600 text-sm">Esta entrada de No Consta ya fue agregada.</div>',
                status=400
            )

        noconsta_cart.append(noconsta_entry)
        request.session['noconsta_cart'] = noconsta_cart

        response = render(request, 'tramites/partials/lista_noconsta_cart.html', {
            'noconsta_cart': noconsta_cart,
        })
        response['HX-Retarget'] = '#noconsta-cart'
        response['HX-Reswap'] = 'outerHTML'
        response['HX-Trigger'] = 'noconsta-changed'
        return response

    if campo_busqueda != 'ruc':
        return HttpResponse(
            '<div class="p-2 text-red-600 text-sm">La búsqueda encontró resultados. Agregue la empresa desde una fila de la tabla.</div>',
            status=400
        )

    return _agregar_empresas_por_ruc(request, ruc)


@login_required
@require_http_methods(["POST"])
def agregar_empresa_desde_resultado_hx(request):
    """Agrega una empresa desde una fila de resultados usando su RUC."""
    return _agregar_empresas_por_ruc(request, request.POST.get('ruc_empresa', '').strip())


@login_required
@require_http_methods(["POST"])
def remover_empresa_por_ruc_hx(request):
    """Remover una empresa del carrito de sesión por RUC (HTMX)."""
    ruc_empresa = request.POST.get('ruc_empresa', '').strip()
    empresas_cart = request.session.get('empresas_cart', [])

    empresas_cart = [e for e in empresas_cart if e.get('ruc_completo') != ruc_empresa]
    request.session['empresas_cart'] = empresas_cart

    response = render(request, 'tramites/partials/lista_empresas_cart.html', {
        'empresas_cart': empresas_cart,
    })
    response['HX-Trigger'] = 'empresas-changed'
    return response


@login_required
@require_http_methods(["DELETE"])
def remover_empresa_hx(request, index):
    """Remover una empresa del carrito de sesión por índice (HTMX)."""
    empresas_cart = request.session.get('empresas_cart', [])

    if 0 <= index < len(empresas_cart):
        empresas_cart.pop(index)
        request.session['empresas_cart'] = empresas_cart

    response = render(request, 'tramites/partials/lista_empresas_cart.html', {
        'empresas_cart': empresas_cart,
    })
    response['HX-Trigger'] = 'empresas-changed'
    return response


@login_required
@require_http_methods(["DELETE"])
def remover_noconsta_hx(request, index):
    """Remover una entrada de No Consta del carrito de sesión por índice (HTMX)."""
    noconsta_cart = _normalizar_noconsta_en_sesion(request)

    if 0 <= index < len(noconsta_cart):
        noconsta_cart.pop(index)
        request.session['noconsta_cart'] = noconsta_cart

    response = render(request, 'tramites/partials/lista_noconsta_cart.html', {
        'noconsta_cart': noconsta_cart,
    })
    response['HX-Trigger'] = 'noconsta-changed'
    return response


@login_required
@require_rol(UsuarioMICI.TRABAJADOR, UsuarioMICI.DIRECTOR)
@require_http_methods(["GET", "POST"])
def editar_pdf_view(request, id):
    """Editar el HTML del PDF de un trámite en revisión."""
    tramite = get_object_or_404(Tramite, uuid=id)

    if tramite.estado != Tramite.EN_REVISION:
        messages.error(request, 'Solo se puede editar el PDF de trámites en revisión.')
        return redirect('tramites:detalle', id=tramite.uuid)

    # HTML completo (original o ya editado)
    html_completo = tramite.html_pdf_editado or generar_html_tramite(tramite)

    if request.method == 'POST':
        contenido_editado = request.POST.get('contenido_editado', '').strip()
        if not contenido_editado:
            messages.error(request, 'El contenido no puede estar vacío.')
            contenido_editable_err = extraer_contenido_editable(html_completo)
            return render(request, 'tramites/editar_pdf.html', {
                'tramite': tramite,
                'contenido_editable': contenido_editable_err,
                'contenido_editable_json': json.dumps(contenido_editable_err),
            })

        # Re-inyectar contenido editado en el HTML completo
        html_final = reinyectar_contenido_editado(html_completo, contenido_editado)

        # Guardar HTML editado
        tramite.html_pdf_editado = html_final
        tramite.save(update_fields=['html_pdf_editado'])

        # Regenerar PDF con el HTML editado
        pdf_bytesio = generar_pdf_desde_html(html_final)
        pdf_content = pdf_bytesio.read()

        pdf_filename = f'tramite_{tramite.uuid}.pdf'
        tramite.archivo_pdf.save(pdf_filename, ContentFile(pdf_content), save=False)
        tramite.save(update_fields=['archivo_pdf'])

        # Registrar evento
        ip_cliente = obtener_ip_cliente(request)
        registrar_evento(
            tipo_evento=BitacoraEvento.CAMBIO_ESTADO,
            actor=request.user,
            ip_origen=ip_cliente,
            recurso=tramite,
            descripcion=f'Edición de HTML del PDF del trámite {tramite.numero_referencia or tramite.uuid}',
            metadata={'accion': 'editar_pdf'}
        )

        messages.success(request, 'PDF actualizado correctamente.')
        return redirect('tramites:detalle', id=tramite.uuid)

    # GET: extraer solo el contenido editable
    contenido_editable = extraer_contenido_editable(html_completo)

    return render(request, 'tramites/editar_pdf.html', {
        'tramite': tramite,
        'contenido_editable': contenido_editable,
        'contenido_editable_json': json.dumps(contenido_editable),
    })


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(["GET", "POST"])
def configurar_secuencias_view(request):
    """Permite al Director ajustar el último número emitido por tipo de documento
    para el año en curso, de modo que la numeración continúe desde un sistema
    anterior. Solo afecta el año actual.
    """
    anio_actual = timezone.now().year
    tipos = ['OFICIO', 'CERTIFICADO']

    secuencias = {}
    for tipo in tipos:
        sec, _ = SecuenciaTramite.objects.get_or_create(
            tipo_documento=tipo,
            anio=anio_actual,
            defaults={'ultimo_numero': 0},
        )
        secuencias[tipo] = sec

    if request.method == 'POST':
        errores = {}
        nuevos_valores = {}

        for tipo in tipos:
            valor_str = request.POST.get(f'ultimo_numero_{tipo}', '').strip()
            try:
                valor = int(valor_str)
                if valor < 0:
                    raise ValueError
            except ValueError:
                errores[tipo] = 'Debe ser un número entero positivo o cero.'
                continue

            # No permitir bajar la secuencia por debajo de números ya emitidos.
            tramites_qs = Tramite.objects.filter(
                tipo_documento=tipo,
                fecha_creacion__year=anio_actual,
            ).values_list('numero_referencia', flat=True)

            max_emitido = 0
            for ref in tramites_qs:
                try:
                    n = int(ref)
                    if n > max_emitido:
                        max_emitido = n
                except (TypeError, ValueError):
                    continue

            if valor < max_emitido:
                errores[tipo] = (
                    f'No puede ser menor que el mayor número ya emitido este año ({max_emitido}). '
                    'Bajarlo generaría duplicados.'
                )
                continue

            nuevos_valores[tipo] = valor

        if errores:
            for tipo, msg in errores.items():
                messages.error(request, f'{tipo.title()}: {msg}')
        else:
            ip_cliente = obtener_ip_cliente(request)
            for tipo, valor in nuevos_valores.items():
                sec = secuencias[tipo]
                anterior = sec.ultimo_numero
                if anterior == valor:
                    continue
                sec.ultimo_numero = valor
                sec.actualizado_por = request.user
                sec.save(update_fields=['ultimo_numero', 'actualizado_por', 'fecha_actualizacion'])
                registrar_evento(
                    tipo_evento=BitacoraEvento.SECUENCIA_AJUSTADA,
                    actor=request.user,
                    ip_origen=ip_cliente,
                    recurso=sec,
                    descripcion=(
                        f'Ajuste de secuencia {tipo} {anio_actual}: '
                        f'{anterior} → {valor}'
                    ),
                    metadata={
                        'tipo_documento': tipo,
                        'anio': anio_actual,
                        'valor_anterior': anterior,
                        'valor_nuevo': valor,
                    },
                )
            messages.success(request, 'Secuencias actualizadas correctamente.')
            return redirect('tramites:configurar_secuencias')

    return render(request, 'tramites/configurar_secuencias.html', {
        'anio_actual': anio_actual,
        'secuencia_oficio': secuencias['OFICIO'],
        'secuencia_certificado': secuencias['CERTIFICADO'],
    })


# =============================================================================
# Gestión de plantillas de membrete (solo Director)
# =============================================================================

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.db import transaction


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
def listar_plantillas_view(request):
    """Lista todas las plantillas disponibles (Director)."""
    plantillas = PlantillaDocumento.objects.select_related('creado_por').all()

    activa_certificado = next(
        (p for p in plantillas if p.activa_certificado),
        None,
    )
    activa_oficio = next(
        (p for p in plantillas if p.activa_oficio),
        None,
    )

    return render(request, 'tramites/plantillas/lista.html', {
        'plantillas': plantillas,
        'activa_certificado': activa_certificado,
        'activa_oficio': activa_oficio,
        'usa_sistema_certificado': activa_certificado is None,
        'usa_sistema_oficio': activa_oficio is None,
    })


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(['GET', 'POST'])
def subir_plantilla_view(request):
    """Sube un .docx, extrae header/footer/márgenes y crea la PlantillaDocumento."""
    if request.method == 'POST':
        form = PlantillaDocumentoSubirForm(request.POST, request.FILES)
        if form.is_valid():
            archivo_word = form.cleaned_data['archivo_word']
            try:
                datos = extraer_plantilla_desde_docx(archivo_word)
            except DjangoValidationError as exc:
                form.add_error('archivo_word', exc.messages[0])
            else:
                plantilla = form.save(commit=False)
                plantilla.creado_por = request.user
                plantilla.preview_visto = False
                plantilla.margen_superior_cm = datos['margen_superior_cm']
                plantilla.margen_inferior_cm = datos['margen_inferior_cm']
                # El sidebar de QR ocupa 2.2cm fijos; forzamos mínimo 2.5cm
                # aunque el .docx traiga un margen menor, para que no invada el contenido.
                plantilla.margen_izquierdo_cm = max(
                    datos['margen_izquierdo_cm'],
                    PlantillaDocumentoMargenesForm.MARGEN_IZQUIERDO_MIN,
                )
                plantilla.margen_derecho_cm = datos['margen_derecho_cm']
                plantilla.imagen_header_ancho_cm = datos.get('imagen_header_ancho_cm')
                plantilla.imagen_header_alto_cm = datos.get('imagen_header_alto_cm')
                plantilla.imagen_footer_ancho_cm = datos.get('imagen_footer_ancho_cm')
                plantilla.imagen_footer_alto_cm = datos.get('imagen_footer_alto_cm')
                plantilla.imagen_marca_agua_ancho_cm = datos.get('imagen_marca_agua_ancho_cm')
                plantilla.imagen_marca_agua_alto_cm = datos.get('imagen_marca_agua_alto_cm')
                plantilla.cuerpo_plantilla_html = datos.get('cuerpo_html', '') or ''
                # Guardamos primero para tener PK y poder usar storage
                archivo_word.seek(0)
                plantilla.archivo_word = archivo_word
                plantilla.imagen_header.save(
                    f'header_{plantilla.nombre[:30]}.png',
                    ContentFile(datos['imagen_header_bytes']),
                    save=False,
                )
                if datos['imagen_footer_bytes']:
                    plantilla.imagen_footer.save(
                        f'footer_{plantilla.nombre[:30]}.png',
                        ContentFile(datos['imagen_footer_bytes']),
                        save=False,
                    )
                if datos.get('imagen_marca_agua_bytes'):
                    plantilla.imagen_marca_agua.save(
                        f'wm_{plantilla.nombre[:30]}.png',
                        ContentFile(datos['imagen_marca_agua_bytes']),
                        save=False,
                    )
                plantilla.save()
                registrar_evento(
                    tipo_evento=BitacoraEvento.PLANTILLA_CREADA,
                    actor=request.user,
                    ip_origen=obtener_ip_cliente(request),
                    recurso=plantilla,
                    descripcion=f'Plantilla "{plantilla.nombre}" creada ({plantilla.get_tipo_aplicable_display()})',
                    metadata={
                        'tipo_aplicable': plantilla.tipo_aplicable,
                        'tiene_footer': bool(datos['imagen_footer_bytes']),
                    },
                )
                messages.success(
                    request,
                    'Plantilla creada. Revisa el preview y ajusta los márgenes antes de activarla.',
                )
                return redirect('tramites:detalle_plantilla', plantilla_id=plantilla.id)
    else:
        form = PlantillaDocumentoSubirForm()

    return render(request, 'tramites/plantillas/subir.html', {'form': form})


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(['GET', 'POST'])
def detalle_plantilla_view(request, plantilla_id):
    """Pantalla de preview + ajuste de márgenes. Marca preview_visto=True al cargar."""
    plantilla = get_object_or_404(PlantillaDocumento, pk=plantilla_id)

    if request.method == 'POST':
        form = PlantillaDocumentoMargenesForm(request.POST, instance=plantilla)
        es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if form.is_valid():
            form.save()
            if es_ajax:
                return HttpResponse(status=204)
            messages.success(request, 'Márgenes actualizados.')
            return redirect('tramites:detalle_plantilla', plantilla_id=plantilla.id)
        elif es_ajax:
            return HttpResponse(status=400)
    else:
        form = PlantillaDocumentoMargenesForm(instance=plantilla)
        # GET: marcar como vista para habilitar el botón de activar
        if not plantilla.preview_visto:
            plantilla.preview_visto = True
            plantilla.save(update_fields=['preview_visto'])

    margenes_campos = [
        (form['margen_superior_cm'], 'Superior'),
        (form['margen_inferior_cm'], 'Inferior'),
        (form['margen_izquierdo_cm'], 'Izquierdo'),
        (form['margen_derecho_cm'], 'Derecho'),
    ]

    activa_certificado = PlantillaDocumento.objects.filter(activa_certificado=True).exclude(pk=plantilla.pk).first()
    activa_oficio = PlantillaDocumento.objects.filter(activa_oficio=True).exclude(pk=plantilla.pk).first()

    return render(request, 'tramites/plantillas/detalle.html', {
        'plantilla': plantilla,
        'form': form,
        'margenes_campos': margenes_campos,
        'activa_certificado': activa_certificado,
        'activa_oficio': activa_oficio,
    })


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(['GET'])
@xframe_options_sameorigin
def preview_plantilla_view(request, plantilla_id):
    """Devuelve un PDF preview generado con datos dummy aplicando la plantilla."""
    plantilla = get_object_or_404(PlantillaDocumento, pk=plantilla_id)
    from .services.generador_pdf import generar_preview_plantilla
    pdf_bytes = generar_preview_plantilla(plantilla)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="preview_plantilla_{plantilla.id}.pdf"'
    return response


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(['POST'])
def toggle_activacion_plantilla_view(request, plantilla_id, tipo):
    """Activa o desactiva una plantilla para un tipo específico (CERTIFICADO|OFICIO)."""
    if tipo not in (PlantillaDocumento.CERTIFICADO, PlantillaDocumento.OFICIO):
        return HttpResponseBadRequest()

    plantilla = get_object_or_404(PlantillaDocumento, pk=plantilla_id)
    accion = request.POST.get('accion')
    campo = 'activa_certificado' if tipo == PlantillaDocumento.CERTIFICADO else 'activa_oficio'
    tipo_label = 'Certificados' if tipo == PlantillaDocumento.CERTIFICADO else 'Oficios'

    if accion == 'activar':
        if not plantilla.preview_visto:
            messages.error(request, 'Debes ver el preview antes de activar la plantilla.')
            return redirect('tramites:listar_plantillas')
        with transaction.atomic():
            desactivadas_ids = list(
                PlantillaDocumento.objects.filter(**{campo: True})
                .exclude(pk=plantilla.pk)
                .values_list('pk', flat=True)
            )
            PlantillaDocumento.objects.filter(pk__in=desactivadas_ids).update(
                **{campo: False},
            )
            setattr(plantilla, campo, True)
            plantilla.fecha_activacion = timezone.now()
            plantilla.save(update_fields=[campo, 'fecha_activacion'])
        registrar_evento(
            tipo_evento=BitacoraEvento.PLANTILLA_ACTIVADA,
            actor=request.user,
            ip_origen=obtener_ip_cliente(request),
            recurso=plantilla,
            descripcion=f'Plantilla "{plantilla.nombre}" activada para {tipo_label}',
            metadata={
                'tipo': tipo,
                'accion': 'activar',
                'desactivadas_ids': desactivadas_ids,
            },
        )
        messages.success(request, f'Plantilla "{plantilla.nombre}" activada para {tipo_label}.')

    elif accion == 'desactivar':
        setattr(plantilla, campo, False)
        plantilla.save(update_fields=[campo])
        registrar_evento(
            tipo_evento=BitacoraEvento.PLANTILLA_ACTIVADA,
            actor=request.user,
            ip_origen=obtener_ip_cliente(request),
            recurso=plantilla,
            descripcion=f'Plantilla "{plantilla.nombre}" desactivada para {tipo_label}',
            metadata={'tipo': tipo, 'accion': 'desactivar'},
        )
        messages.success(
            request,
            f'Plantilla "{plantilla.nombre}" desactivada para {tipo_label}. Los nuevos trámites usarán la plantilla del sistema.',
        )
    else:
        return HttpResponseBadRequest()

    return redirect('tramites:listar_plantillas')


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(['POST'])
def eliminar_plantilla_view(request, plantilla_id):
    """Elimina una plantilla inactiva. Bloqueado para plantillas activas."""
    plantilla = get_object_or_404(PlantillaDocumento, pk=plantilla_id)

    if plantilla.activa:
        messages.error(
            request,
            'No se puede eliminar una plantilla activa. Desactívala primero.',
        )
        return redirect('tramites:listar_plantillas')

    nombre = plantilla.nombre
    tipo = plantilla.tipo_aplicable
    plantilla_id_eliminada = plantilla.pk
    plantilla.delete()
    registrar_evento(
        tipo_evento=BitacoraEvento.PLANTILLA_ELIMINADA,
        actor=request.user,
        ip_origen=obtener_ip_cliente(request),
        recurso=None,
        descripcion=f'Plantilla "{nombre}" eliminada',
        metadata={
            'plantilla_id': plantilla_id_eliminada,
            'nombre': nombre,
            'tipo_aplicable': tipo,
        },
    )
    messages.success(request, f'Plantilla "{nombre}" eliminada.')
    return redirect('tramites:listar_plantillas')
