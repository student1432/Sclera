# academic_data.py
# System-controlled academic backbone - Now using modular structure
# Students CANNOT edit this data

# Import from new modular structure for better performance
from .academic_data import (
    ACADEMIC_SYLLABI,
    get_syllabus,
    get_available_subjects,
    get_cbse_data,
    get_exam_data
)

# Re-export for backward compatibility
__all__ = [
    'ACADEMIC_SYLLABI',
    'get_syllabus',
    'get_available_subjects',
    'get_cbse_data', 
    'get_exam_data'
]
