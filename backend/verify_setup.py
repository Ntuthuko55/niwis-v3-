#!/usr/bin/env python
"""Verify trend analysis module and backend endpoints are working"""
import sys

try:
    from app.main import app
    print("SUCCESS: FastAPI app loaded successfully")
    
    # Get routes
    routes = [route.path for route in app.routes if hasattr(route, 'path')]
    trend_routes = [r for r in routes if 'trend' in r]
    
    print(f"\nTrend analysis endpoints ({len(trend_routes)}):")
    for route in sorted(trend_routes):
        print(f"  - {route}")
    
    print(f"\nTotal API endpoints: {len(routes)}")
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
