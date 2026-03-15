from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.conf import settings
from pathlib import Path
import os
from .models import Tramite, PreguntaOficio
from .services.generador_pdf import generar_pdf_tramite, calcular_hash_pdf
from identidad.decorators import require_rol
from identidad.models import UsuarioMICI
from integracion.services import buscar_empresa
from integracion.adapters import normalizar_datos_empresa, construir_ubicacion_completa
from auditoria.services import registrar_evento, obtener_ip_cliente
from auditoria.models import BitacoraEvento


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

        # Empresas del carrito en sesión
        empresas_cart = request.session.get('empresas_cart', [])

        # Oficios requieren al menos 1 empresa
        if tipo_documento == 'OFICIO' and not empresas_cart:
            messages.error(request, 'Debe agregar al menos una empresa para crear un oficio.')
            return redirect('consultar_tramite')

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
        origen_consulta = ', '.join(e.get('ruc_completo', e.get('ruc', '')) for e in empresas_cart) if empresas_cart else ''

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
            origen_consulta=origen_consulta,
            numero_referencia=f"{tipo_documento[:3]}-{timezone.now().strftime('%Y%m%d')}-{Tramite.objects.count() + 1}",
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

        # Limpiar carrito de sesión
        request.session.pop('empresas_cart', None)

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

    # GET: limpiar carrito y mostrar selector de tipo
    request.session.pop('empresas_cart', None)
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

    return render(request, 'tramites/partials/formulario_tipo.html', {
        'tipo_documento': tipo_documento,
        'tipo_label': tipo_labels[tipo_documento],
        'empresas_cart': empresas_cart,
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
            metadata={'estado_anterior': estado_anterior, 'revisor': request.user.username}
        )
        
        # Generar PDF al aprobar
        pdf_bytesio = generar_pdf_tramite(tramite)
        pdf_content = pdf_bytesio.read()

        temp_pdf_dir = Path(__file__).parent / 'temp_pdfs'
        temp_pdf_dir.mkdir(exist_ok=True)
        pdf_filename = f'tramite_{tramite.uuid}.pdf'
        pdf_path = temp_pdf_dir / pdf_filename

        with open(pdf_path, 'wb') as f:
            f.write(pdf_content)

        tramite.archivo_pdf.name = f'temp_pdfs/{pdf_filename}'
        tramite.save()

        messages.success(request, 'Trámite aprobado correctamente.')
    except Exception as e:
        messages.error(request, str(e))

    return redirect('tramites:detalle', id=tramite.uuid)


@login_required
@require_rol(UsuarioMICI.DIRECTOR)
@require_http_methods(["GET", "POST"])
def firmar_view(request, id):
    """Firmar un trámite aprobado: descargar PDF, firmar externamente y subirlo."""
    tramite = get_object_or_404(Tramite, uuid=id)
    
    if tramite.estado != Tramite.APROBADO:
        messages.error(request, f'El trámite debe estar aprobado para poder firmarlo.')
        return redirect('tramites:detalle', id=tramite.uuid)
    
    if request.method == 'POST':
        # Validar que se haya subido un archivo
        if 'archivo_pdf_firmado' not in request.FILES:
            messages.error(request, 'Debe subir el PDF firmado.')
            return render(request, 'tramites/firmar.html', {'tramite': tramite})
        
        archivo_subido = request.FILES['archivo_pdf_firmado']
        
        # Validar que sea PDF
        if not archivo_subido.name.lower().endswith('.pdf'):
            messages.error(request, 'El archivo debe ser un PDF (.pdf).')
            return render(request, 'tramites/firmar.html', {'tramite': tramite})
        
        # Validar tamaño (máximo 10MB)
        if archivo_subido.size > 10 * 1024 * 1024:
            messages.error(request, 'El archivo PDF no puede exceder 10MB.')
            return render(request, 'tramites/firmar.html', {'tramite': tramite})
        
        try:
            estado_anterior = tramite.estado
            
            # Leer contenido del PDF subido
            pdf_content = archivo_subido.read()
            
            # Calcular hash SHA-256 del PDF firmado
            hash_documento = calcular_hash_pdf(pdf_content)
            
            # Guardar PDF firmado en carpeta temporal
            temp_pdf_dir = Path(__file__).parent / 'temp_pdfs' / 'firmados'
            temp_pdf_dir.mkdir(parents=True, exist_ok=True)
            
            pdf_filename = f'tramite_{tramite.uuid}_firmado.pdf'
            pdf_path = temp_pdf_dir / pdf_filename
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)
            
            # Resetear el archivo para guardarlo en el modelo
            archivo_subido.seek(0)
            
            # Guardar en el modelo usando el FileField
            tramite.archivo_pdf_firmado.save(pdf_filename, archivo_subido, save=False)
            
            # Marcar como firmado con el hash (el archivo ya está guardado)
            tramite.marcar_firmado(request.user, hash_documento=hash_documento)
            
            # Registrar evento de firma
            ip_cliente = obtener_ip_cliente(request)
            registrar_evento(
                tipo_evento=BitacoraEvento.FIRMA,
                actor=request.user,
                ip_origen=ip_cliente,
                recurso=tramite,
                descripcion=f'Firma de documento - Estado anterior: {estado_anterior}',
                metadata={'estado_anterior': estado_anterior, 'hash': hash_documento, 'archivo': pdf_filename}
            )
            
            messages.success(request, 'PDF firmado subido correctamente. El trámite ha sido marcado como firmado.')
            return redirect('tramites:detalle', id=tramite.uuid)
        except Exception as e:
            messages.error(request, f'Error al procesar el PDF firmado: {str(e)}')
    
    return render(request, 'tramites/firmar.html', {
        'tramite': tramite
    })


@login_required
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
    
    # Determinar qué PDF servir: firmado si existe, sino el original
    try:
        pdf_content = None
        pdf_filename = f'tramite_{tramite.uuid}.pdf'
        
        # Prioridad 1: PDF firmado si existe y el trámite está firmado
        if tramite.estado == Tramite.FIRMADO and tramite.archivo_pdf_firmado and tramite.archivo_pdf_firmado.name:
            pdf_path = Path(__file__).parent / 'temp_pdfs' / 'firmados' / f'tramite_{tramite.uuid}_firmado.pdf'
            if pdf_path.exists():
                with open(pdf_path, 'rb') as f:
                    pdf_content = f.read()
                pdf_filename = f'tramite_{tramite.uuid}_firmado.pdf'
        
        # Prioridad 2: PDF original si existe
        if not pdf_content and tramite.archivo_pdf and tramite.archivo_pdf.name:
            pdf_path = Path(__file__).parent / tramite.archivo_pdf.name
            if pdf_path.exists():
                with open(pdf_path, 'rb') as f:
                    pdf_content = f.read()
        
        # Prioridad 3: Generar PDF si no existe ninguno
        if not pdf_content:
            pdf_bytesio = generar_pdf_tramite(tramite)
            pdf_content = pdf_bytesio.read()
            
            # Guardar PDF generado en carpeta temporal
            temp_pdf_dir = Path(__file__).parent / 'temp_pdfs'
            temp_pdf_dir.mkdir(exist_ok=True)
            pdf_path = temp_pdf_dir / pdf_filename
            
            with open(pdf_path, 'wb') as f:
                f.write(pdf_content)
            
            # Actualizar modelo si no tenía archivo
            if not tramite.archivo_pdf or not tramite.archivo_pdf.name:
                tramite.archivo_pdf.name = f'temp_pdfs/{pdf_filename}'
                tramite.save()
        
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
        
        # Servir el PDF
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'{content_disposition}; filename="{pdf_filename}"'
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
    """Agregar todos los avisos de un RUC al carrito de sesión (HTMX)."""
    ruc_input = request.POST.get('ruc_empresa', '').strip()
    ruc = "-".join(ruc_input.split("-")[:3])

    if not ruc:
        return HttpResponse('<div class="p-2 text-red-600 text-sm">Debe ingresar un RUC.</div>', status=400)

    resultado = buscar_empresa(ruc)
    if not resultado:
        return HttpResponse('<div class="p-2 text-red-600 text-sm">No se encontró empresa con ese RUC.</div>', status=404)

    empresas_cart = request.session.get('empresas_cart', [])

    # Normalizar TODOS los resultados raw
    nuevas_empresas = []
    for raw in resultado['resultados_raw']:
        emp = normalizar_datos_empresa(raw)
        emp['ubicacion_completa'] = construir_ubicacion_completa(emp)
        nuevas_empresas.append(emp)

    # Dedup por numero_aviso
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
