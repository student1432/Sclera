#!/usr/bin/env python
"""
WSGI entry point for Sclera standalone deployment
"""
import sys
import os
import importlib.util

# Load sclera.py directly to avoid app/ directory conflicts
spec = importlib.util.spec_from_file_location("sclera_module", os.path.join(os.path.dirname(__file__), "sclera.py"))
sclera_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sclera_module)

# Get Flask application instance
app = sclera_module.app

if __name__ == "__main__":
    app.run()
