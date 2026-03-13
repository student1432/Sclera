"""
sclera_phase2_routes.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 2 — Enhanced Teacher Tools
Paste these routes into sclera.py (after the existing institution routes, before
the error handlers / before `if __name__ == '__main__':`).

Also add to sclera.py imports at the top:
    from report_generator import generate_class_report_pdf, generate_student_report_pdf
    import io, json
    try:
        import pdfplumber
        PDFPLUMBER_AVAILABLE = True
    except ImportError:
        PDFPLUMBER_AVAILABLE = False
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

