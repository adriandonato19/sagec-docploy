"""
Mock data actualizado basado en el JSON proporcionado por el usuario.

Este módulo simula la respuesta de la API de Panamá Emprende.
"""

MOCK_EMPRESAS_API = [
  {
    "aviso_operacion": "573584-2025",
    "numero_licencia": "707200408",
    "razon_comercial": "PANAMA ATV STORE",
    "representante_legal": "LUIS GABRIEL ORTEGA",
    "ruc": "5735841-447039",
    "dv": "89",
    "razon_social": "XTREME STORE, S.A.",
    "fecha_inicio_operaciones": "01/01/2020",
    "provincia": "PANAMÁ",
    "distrito": "PANAMÁ",
    "corregimiento": "SAN FRANCISCO",
    "urbanizacion": "PUNTA PACIFICA",
    "calle": "PRINCIPAL",
    "casa": "",
    "edificio": "PANAMA ATV STORE",
    "apartamento": "No.1",
    "actividad_comercial": "COMPRA Y VENTA DE MOTOS Y REPUESTOS",
    "ciiu": "4540",
    "capital_invertido": 5000.00,
    "estado_sucursal": "CANCELADO",
    "sucursal": "001"
  },
  {
    "aviso_operacion": "123456-2025",
    "numero_licencia": "808300509",
    "razon_comercial": "TECNOLOGÍA AVANZADA",
    "representante_legal": "MARÍA PÉREZ",
    "ruc": "1234567-1-123456",
    "dv": "10",
    "razon_social": "SOLUCIONES TECH, S.A.",
    "fecha_inicio_operaciones": "15/03/2021",
    "provincia": "PANAMÁ",
    "distrito": "PANAMÁ",
    "corregimiento": "BELLA VISTA",
    "urbanizacion": "CALLE 50",
    "calle": "AVENIDA SUR",
    "casa": "M-45",
    "edificio": "TORRE EMPRESARIAL",
    "apartamento": "12-B",
    "actividad_comercial": "CONSULTORÍA INFORMÁTICA",
    "ciiu": "6202",
    "capital_invertido": 15000.00,
    "estado_sucursal": "VIGENTE",
    "sucursal": "002"
  },
  {
    "aviso_operacion": "987654-2025",
    "numero_licencia": "909400610",
    "razon_comercial": "REST. EL DORADO",
    "representante_legal": "JUAN CASTILLO",
    "ruc": "9876543-2-987654",
    "dv": "45",
    "razon_social": "INVERSIONES GASTRONÓMICAS, INC.",
    "fecha_inicio_operaciones": "10/05/2019",
    "provincia": "PANAMÁ",
    "distrito": "PANAMÁ",
    "corregimiento": "BETANIA",
    "urbanizacion": "EL DORADO",
    "calle": "CALLE 74",
    "casa": "12",
    "edificio": "",
    "apartamento": "",
    "actividad_comercial": "SERVICIOS DE RESTAURANTE",
    "ciiu": "5610",
    "capital_invertido": 25000.00,
    "estado_sucursal": "VIGENTE",
    "sucursal": "003"
  },
  {
    "aviso_operacion": "456123-2025",
    "numero_licencia": "505600711",
    "razon_comercial": "CONSTRUCTORA DEL ISTMO",
    "representante_legal": "CARLOS RÍOS",
    "ruc": "4561234-1-456123",
    "dv": "22",
    "razon_social": "DESARROLLOS URBANOS, S.A.",
    "fecha_inicio_operaciones": "20/08/2022",
    "provincia": "COLÓN",
    "distrito": "COLÓN",
    "corregimiento": "CRISTÓBAL",
    "urbanizacion": "ZONA LIBRE",
    "calle": "AVENIDA CENTRAL",
    "casa": "",
    "edificio": "LOCAL 4",
    "apartamento": "",
    "actividad_comercial": "CONSTRUCCIÓN DE EDIFICIOS",
    "ciiu": "4100",
    "capital_invertido": 100000.00,
    "estado_sucursal": "EN SOLICITUD",
    "sucursal": "004"
  },
  {
    "aviso_operacion": "789321-2025",
    "numero_licencia": "606700812",
    "razon_comercial": "MINI SUPER LA BENDICIÓN",
    "representante_legal": "ANA GÓMEZ",
    "ruc": "8-765-4321",
    "dv": "00",
    "razon_social": "ANA GÓMEZ PERSONA NATURAL",
    "fecha_inicio_operaciones": "12/12/2018",
    "provincia": "CHIRIQUÍ",
    "distrito": "DAVID",
    "corregimiento": "DAVID CABECERA",
    "urbanizacion": "BARRIO SUR",
    "calle": "CALLE 4TA",
    "casa": "H-2",
    "edificio": "",
    "apartamento": "",
    "actividad_comercial": "VENTA DE VÍVERES AL POR MENOR",
    "ciiu": "4711",
    "capital_invertido": 2000.00,
    "estado_sucursal": "VIGENTE",
    "sucursal": "005"
  },
  {
    "aviso_operacion": "321654-2025",
    "numero_licencia": "404500913",
    "razon_comercial": "FARMACIA SAN JUDAS",
    "representante_legal": "ELENA MARÍN",
    "ruc": "3216549-1-321654",
    "dv": "11",
    "razon_social": "SALUD Y VIDA, S.A.",
    "fecha_inicio_operaciones": "05/01/2023",
    "provincia": "PANAMÁ OESTE",
    "distrito": "LA CHORRERA",
    "corregimiento": "BARRIO BALBOA",
    "urbanizacion": "CENTRAL",
    "calle": "AVENIDA DE LAS AMÉRICAS",
    "casa": "",
    "edificio": "PLAZA LIBERTAD",
    "apartamento": "LOCAL 5",
    "actividad_comercial": "VENTA DE PRODUCTOS FARMACÉUTICOS",
    "ciiu": "4772",
    "capital_invertido": 12000.00,
    "estado_sucursal": "VIGENTE",
    "sucursal": "006"
  },
  {
    "aviso_operacion": "654987-2025",
    "numero_licencia": "303401014",
    "razon_comercial": "LOGÍSTICA TOTAL",
    "representante_legal": "ROBERTO SÁNCHEZ",
    "ruc": "6549871-2-654987",
    "dv": "99",
    "razon_social": "CARGO PANAMÁ CORP.",
    "fecha_inicio_operaciones": "18/06/2020",
    "provincia": "PANAMÁ",
    "distrito": "PANAMÁ",
    "corregimiento": "JUAN DÍAZ",
    "urbanizacion": "COSTA DEL ESTE",
    "calle": "AVENIDA PRINCIPAL",
    "casa": "",
    "edificio": "BUSINESS PARK",
    "apartamento": "OFICINA 203",
    "actividad_comercial": "TRANSPORTE Y ALMACENAJE",
    "ciiu": "5210",
    "capital_invertido": 50000.00,
    "estado_sucursal": "CANCELADO",
    "sucursal": "007"
  },
  {
    "aviso_operacion": "159753-2025",
    "numero_licencia": "202301115",
    "razon_comercial": "TALLER LOS AMIGOS",
    "representante_legal": "PEDRO ALVARADO",
    "ruc": "4-123-456",
    "dv": "01",
    "razon_social": "PEDRO ALVARADO SERVICIOS",
    "fecha_inicio_operaciones": "22/11/2015",
    "provincia": "HERRERA",
    "distrito": "CHITRÉ",
    "corregimiento": "CHITRÉ CABECERA",
    "urbanizacion": "EL ROSARIO",
    "calle": "CALLE ABAJO",
    "casa": "33",
    "edificio": "",
    "apartamento": "",
    "actividad_comercial": "REPARACIÓN DE VEHÍCULOS MOTORIZADOS",
    "ciiu": "4520",
    "capital_invertido": 3500.00,
    "estado_sucursal": "VIGENTE",
    "sucursal": "008"
  },
  {
    "aviso_operacion": "852456-2025",
    "numero_licencia": "101201216",
    "razon_comercial": "BOUTIQUE ELEGANCE",
    "representante_legal": "LUCÍA MÉNDEZ",
    "ruc": "8524567-1-852456",
    "dv": "33",
    "razon_social": "MODA Y ESTILO, S.A.",
    "fecha_inicio_operaciones": "01/09/2024",
    "provincia": "COCLÉ",
    "distrito": "PENONOMÉ",
    "corregimiento": "PENONOMÉ CABECERA",
    "urbanizacion": "CENTRO",
    "calle": "CALLE DAMIÁN CARLES",
    "casa": "",
    "edificio": "MALL IGUANA",
    "apartamento": "LOCAL 12",
    "actividad_comercial": "VENTA DE ROPA AL POR MENOR",
    "ciiu": "4771",
    "capital_invertido": 8000.00,
    "estado_sucursal": "EN SOLICITUD",
    "sucursal": "009"
  },
  {
    "aviso_operacion": "753159-2025",
    "numero_licencia": "111222333",
    "razon_comercial": "IMPORTADORA ORIENTE",
    "representante_legal": "LI CHEN",
    "ruc": "7531590-2-753159",
    "dv": "77",
    "razon_social": "ORIENTE TRADING GROUP",
    "fecha_inicio_operaciones": "14/02/2017",
    "provincia": "COLÓN",
    "distrito": "COLÓN",
    "corregimiento": "BARRIO SUR",
    "urbanizacion": "CENTRO",
    "calle": "CALLE 13",
    "casa": "LOCAL A",
    "edificio": "EDIFICIO CHINO",
    "apartamento": "",
    "actividad_comercial": "IMPORTACIÓN DE PRODUCTOS VARIOS",
    "ciiu": "4690",
    "capital_invertido": 60000.00,
    "estado_sucursal": "VIGENTE",
    "sucursal": "010"
  }
]

def buscar_por_ruc(query):
    """
    Busca datos de empresa por RUC o Aviso de Operación (mock).
    
    Args:
        query: RUC o Aviso a buscar
    
    Returns:
        dict con 'detalle' y 'avisos' o None si no se encuentra
    """
    query_clean = query.replace('-', '').replace(' ', '').strip().upper()
    
    resultados = []
    for empresa in MOCK_EMPRESAS_API:
        ruc_clean = str(empresa['ruc']).replace('-', '').replace(' ', '').upper()
        aviso_clean = str(empresa['aviso_operacion']).replace('-', '').replace(' ', '').upper()
        
        if query_clean in ruc_clean or query_clean in aviso_clean:
            resultados.append(empresa)
    
    if not resultados:
        return None
    
    # Usamos el primer resultado como "detalle principal"
    # y todos los resultados como la lista de "avisos/sucursales"
    return {
        'detalle': resultados[0],
        'avisos': resultados
    }
