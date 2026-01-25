from django.urls import path
from . import views

app_name = 'identidad'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('registro/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('configuracion/', views.perfil_view, name='perfil'),
]

