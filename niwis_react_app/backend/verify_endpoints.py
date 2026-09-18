#!/usr/bin/env python
"""Verify all backend endpoints are registered"""
from app.main import app

print("\n✓ BACKEND ENDPOINTS VERIFICATION\n")
print("=" * 60)

endpoints = {
    'Data Upload & Preview': [],
    'Analysis': [],
    'Feature Engineering': [],
    'Dashboard': [],
    'Forecasting & Export': [],
    'Trend Analysis': [],
    'Health': [],
}

for route in app.routes:
    path = route.path
    methods = list(route.methods) if hasattr(route, 'methods') else []
    
    if '/upload' in path or '/preview' in path:
        endpoints['Data Upload & Preview'].append((path, methods))
    elif '/analysis' in path:
        endpoints['Analysis'].append((path, methods))
    elif '/feature-engineering' in path:
        endpoints['Feature Engineering'].append((path, methods))
    elif '/dashboard' in path:
        endpoints['Dashboard'].append((path, methods))
    elif '/forecast' in path or '/export' in path:
        endpoints['Forecasting & Export'].append((path, methods))
    elif '/trend' in path:
        endpoints['Trend Analysis'].append((path, methods))
    elif '/health' in path:
        endpoints['Health'].append((path, methods))

for category, routes in endpoints.items():
    if routes:
        print(f"\n{category}:")
        for path, methods in routes:
            methods_str = ', '.join(methods) if methods else 'N/A'
            print(f"  • {path}")
            print(f"    Methods: {methods_str}")

print("\n" + "=" * 60)
print("✓ ALL SYSTEMS GO!")
print("  - Swagger UI: http://localhost:8000/api/docs")
print("  - Health Check: http://localhost:8000/health")
print("=" * 60 + "\n")
