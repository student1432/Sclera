# Academic Data Module
# Modular academic syllabus data for different boards, grades, and exams

from .highschool.hs_cbse_8 import HS_CBSE_8_DATA
from .highschool.hs_icse_8 import HS_ICSE_8_DATA
from .highschool.hs_ib_8 import HS_IB_8_DATA
from .highschool.hs_igcse_8 import HS_IGCSE_8_DATA
from .highschool.hs_cbse_9 import HS_CBSE_9_DATA
from .highschool.hs_icse_9 import HS_ICSE_9_DATA
from .highschool.hs_ib_9 import HS_IB_9_DATA
from .highschool.hs_igcse_9 import HS_IGCSE_9_DATA
from .highschool.hs_cbse_10 import HS_CBSE_10_DATA
from .highschool.hs_icse_10 import HS_ICSE_10_DATA
from .highschool.hs_ib_10 import HS_IB_10_DATA
from .highschool.hs_igcse_10 import HS_IGCSE_10_DATA
from .highschool.cbse_11_pcm import CBSE_11_PCM_DATA
from .highschool.cbse_11_pcb import CBSE_11_PCB_DATA
from .highschool.cbse_11_pcmb import CBSE_11_PCMB_DATA
from .highschool.cbse_11_commat import CBSE_11_COMMAT_DATA
from .highschool.cbse_11_com import CBSE_11_COM_DATA
from .highschool.cbse_12_pcm import CBSE_12_PCM_DATA
from .highschool.cbse_12_pcb import CBSE_12_PCB_DATA
from .highschool.cbse_12_pcmb import CBSE_12_PCMB_DATA
from .highschool.cbse_12_commat import CBSE_12_COMMAT_DATA
from .highschool.cbse_12_com import CBSE_12_COM_DATA
from .exams.ep_jee import EP_JEE_DATA
from .exams.ep_neet import EP_NEET_DATA

# Reconstruct ACADEMIC_SYLLABI structure for backward compatibility
ACADEMIC_SYLLABI = {
    'highschool': {
        'CBSE': {
            '8': HS_CBSE_8_DATA,
            '9': HS_CBSE_9_DATA,
            '10': HS_CBSE_10_DATA,
            '11_PCM': CBSE_11_PCM_DATA,
            '11_PCB': CBSE_11_PCB_DATA,
            '11_PCMB': CBSE_11_PCMB_DATA,
            '11_COMMAT': CBSE_11_COMMAT_DATA,
            '11_COM': CBSE_11_COM_DATA,
            '12_PCM': CBSE_12_PCM_DATA,
            '12_PCB': CBSE_12_PCB_DATA,
            '12_PCMB': CBSE_12_PCMB_DATA,
            '12_COMMAT': CBSE_12_COMMAT_DATA,
            '12_COM': CBSE_12_COM_DATA,
        },
        'ICSE': {
            '8': HS_ICSE_8_DATA,
            '9': HS_ICSE_9_DATA,
            '10': HS_ICSE_10_DATA,
        },
        'IB': {
            '8': HS_IB_8_DATA,
            '9': HS_IB_9_DATA,
            '10': HS_IB_10_DATA,
        },
        'IGCSE': {
            '8': HS_IGCSE_8_DATA,
            '9': HS_IGCSE_9_DATA,
            '10': HS_IGCSE_10_DATA,
        },
    },
    'exams': {
        'JEE': EP_JEE_DATA,
        'NEET': EP_NEET_DATA,
    }
}

def get_syllabus(purpose, board_or_exam, grade=None, subjects=None, subject_combination=None):
    """
    Get the syllabus dictionary based on purpose, board/exam, grade, and subject combination.
    Optional: subjects list for after_tenth purpose.
    Optional: subject_combination for CBSE 11-12.
    
    This function maintains the same API as the original for backward compatibility.
    """
    if purpose == 'school':
        # board_or_exam is board (e.g., 'CBSE'), grade is '8', '9', '10', '11', '12'
        grade_str = str(grade) if grade else None
        
        # Get board data, fallback to CBSE if board not found (e.g., ICSE, State Board)
        highschool_data = ACADEMIC_SYLLABI.get('highschool', {})
        board_data = highschool_data.get(board_or_exam)
        if not board_data:
             # Fallback to CBSE if specific board data is missing
             board_data = highschool_data.get('CBSE', {})
             
        # Handle CBSE 11-12 subject combinations
        if board_or_exam == 'CBSE' and grade_str in ['11', '12'] and subject_combination:
            grade_key = f"{grade_str}_{subject_combination}"
            return board_data.get(grade_key, {})
        else:
            return board_data.get(grade_str, {})
    
    elif purpose == 'exam' or purpose == 'exams':
        # board_or_exam is exam type (e.g., 'JEE', 'NEET')
        return ACADEMIC_SYLLABI.get('exams', {}).get(board_or_exam, {})
    
    return {}

def get_available_subjects(purpose, board_or_exam, grade=None):
    """Get list of available subjects for a given academic path"""
    syllabus = get_syllabus(purpose, board_or_exam, grade)
    return list(syllabus.keys()) if syllabus else []

# Lazy loading functions for better performance
def get_cbse_data(grade):
    """Load CBSE data for a specific grade on demand"""
    return ACADEMIC_SYLLABI['highschool']['CBSE'].get(str(grade), {})

def get_exam_data(exam_name):
    """Load exam data for a specific exam on demand"""
    return ACADEMIC_SYLLABI['exams'].get(exam_name, {})

# Export all the necessary components
__all__ = [
    'ACADEMIC_SYLLABI',
    'get_syllabus', 
    'get_available_subjects',
    'get_cbse_data',
    'get_exam_data',
    'CBSE_9_DATA',
    'CBSE_10_DATA', 
    'CBSE_11_DATA',
    'CBSE_12_DATA',
    'JEE_DATA',
    'NEET_DATA'
]
