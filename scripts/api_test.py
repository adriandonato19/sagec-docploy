#!/usr/bin/env python3
"""
Script standalone para probar la conexión con la API de Panamá Emprende.

Uso:
    python scripts/api_test.py <busqueda>

Ejemplo:
    python scripts/api_test.py 155700944
    python scripts/api_test.py "TECNOLOGÍA AVANZADA"
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env')

API_URL = 'https://api.panamaemprende.gob.pa/api/consulta/multiple/{busqueda}'
X_USER = os.environ.get('X-USER', '')
X_PASSWORD = os.environ.get('X-PASSWORD', '')


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/api_test.py <busqueda>")
        print("Ejemplo: python scripts/api_test.py 155700944")
        sys.exit(1)

    busqueda = sys.argv[1]

    if not X_USER or not X_PASSWORD:
        print("ERROR: Variables X-USER y/o X-PASSWORD no encontradas en .env")
        sys.exit(1)

    url = API_URL.format(busqueda=busqueda)
    headers = {
        'X-User': X_USER,
        'X-Password': X_PASSWORD,
    }

    print(f"Consultando: {url}")
    print(f"Headers: X-User={X_USER}")
    print("-" * 60)

    try:
        response = requests.get(url, headers=headers, timeout=20)
        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print("-" * 60)

        if response.status_code == 200:
            data = response.json()
            if data:
                print(json.dumps(data, indent=2, ensure_ascii=False))
                if isinstance(data, list):
                    print(f"\nTotal resultados: {len(data)}")
            else:
                print("Sin resultados.")
        else:
            print(f"Error HTTP {response.status_code}")
            print(response.text)

    except requests.exceptions.Timeout:
        print("ERROR: Timeout - la API no respondió en 15 segundos.")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("ERROR: No se pudo conectar a la API. Verifique su conexión a internet.")
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except ValueError:
        print("ERROR: La respuesta no es JSON válido.")
        print(response.text[:500])
        sys.exit(1)


if __name__ == '__main__':
    main()
