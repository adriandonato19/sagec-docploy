"""
Script para crear usuarios de prueba con los distintos roles.

Uso:
    python manage.py shell < scripts/crear_usuarios_prueba.py
"""
from identidad.models import UsuarioMICI

usuarios = [
    {
        'username': 'fiscal_test',
        'first_name': 'María',
        'last_name': 'González',
        'email': 'fiscal@test.com',
        'cedula': '8-000-0001',
        'rol': UsuarioMICI.FISCAL,
        'institucion': 'Ministerio Público',
        'password': 'Test1234!',
    },
    {
        'username': 'trabajador_test',
        'first_name': 'Carlos',
        'last_name': 'Rodríguez',
        'email': 'trabajador@test.com',
        'cedula': '8-000-0002',
        'rol': UsuarioMICI.TRABAJADOR,
        'institucion': 'MICI',
        'password': 'Test1234!',
    },
    {
        'username': 'director_test',
        'first_name': 'Ana',
        'last_name': 'Martínez',
        'email': 'director@test.com',
        'cedula': '8-000-0003',
        'rol': UsuarioMICI.DIRECTOR,
        'institucion': 'MICI',
        'password': 'Test1234!',
    },
]

for datos in usuarios:
    password = datos.pop('password')
    usuario, created = UsuarioMICI.objects.get_or_create(
        username=datos['username'],
        defaults=datos,
    )
    if created:
        usuario.set_password(password)
        usuario.save()
        print(f"Creado: {usuario.username} | Rol: {usuario.rol} | Password: {password}")
    else:
        print(f"Ya existe: {usuario.username} | Rol: {usuario.rol}")

print("\nResumen de usuarios de prueba:")
print("-" * 50)
for u in UsuarioMICI.objects.filter(username__endswith='_test'):
    print(f"  {u.username:<20} {u.rol:<12} puede_aprobar={u.puede_aprobar}  puede_firmar={u.puede_firmar}")
