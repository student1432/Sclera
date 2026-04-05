#!/usr/bin/env python3
"""
Quick Cache Management CLI for Sclera Academic
Direct cache operations without needing to run the web server
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.cache import (
    clear_ai_cache_for_student,
    clear_ai_cache_for_class, 
    clear_all_ai_cache,
    list_cache_keys,
    clear_cache_for_pattern
)

def check_model_status():
    """Check AI model status"""
    try:
        from gemini_analytics import gemini_analytics
        status = gemini_analytics.get_model_status()
        print("=== AI Model Status ===")
        print(f"Available models: {len(status['available_models'])}")
        for i, model in enumerate(status['available_models']):
            marker = "→ CURRENT" if i == status['current_model_index'] else "  "
            exhausted = " (EXHAUSTED)" if model in status['exhausted_models'] else ""
            print(f"{marker} {model}{exhausted}")
        print(f"Exhausted models: {len(status['exhausted_models'])}")
        print(f"Current model index: {status['current_model_index']}")
    except Exception as e:
        print(f"Error checking model status: {e}")

def reset_models():
    """Reset exhausted AI models"""
    try:
        from gemini_analytics import gemini_analytics
        gemini_analytics.exhausted_models.clear()
        gemini_analytics.current_model_index = 0
        print("✓ AI models reset successfully")
    except Exception as e:
        print(f"Error resetting models: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python cache_cli.py clear-student <uid>")
        print("  python cache_cli.py clear-class <class_id>")
        print("  python cache_cli.py clear-all")
        print("  python cache_cli.py list [pattern]")
        print("  python cache_cli.py clear-pattern <pattern>")
        print("  python cache_cli.py model-status")
        print("  python cache_cli.py reset-models")
        return
    
    command = sys.argv[1].lower()
    
    if command == "clear-student":
        if len(sys.argv) < 3:
            print("Error: Student UID required")
            return
        uid = sys.argv[2]
        clear_ai_cache_for_student(uid)
    
    elif command == "clear-class":
        if len(sys.argv) < 3:
            print("Error: Class ID required")
            return
        class_id = sys.argv[2]
        clear_ai_cache_for_class(class_id)
    
    elif command == "clear-all":
        clear_all_ai_cache()
    
    elif command == "list":
        pattern = sys.argv[2] if len(sys.argv) > 2 else None
        keys = list_cache_keys(pattern)
        print(f"Found {len(keys)} cache keys:")
        for key in keys:
            print(f"  {key}")
    
    elif command == "clear-pattern":
        if len(sys.argv) < 3:
            print("Error: Pattern required")
            return
        pattern = sys.argv[2]
        clear_cache_for_pattern(pattern)
    
    elif command == "model-status":
        check_model_status()
    
    elif command == "reset-models":
        reset_models()
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
