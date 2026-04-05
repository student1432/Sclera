"""
Caching utilities for StudyOS
Provides disk-based caching for frequently accessed data
"""
import diskcache
import hashlib
import json
from functools import wraps
from typing import Any, Optional
from config import Config

# Initialize cache
cache = diskcache.Cache(Config.CACHE_DIR)


class CacheManager:
    """Cache manager for handling cached data"""
    
    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Get value from cache"""
        return cache.get(key)
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = None) -> bool:
        """Set value in cache with optional timeout"""
        try:
            if timeout:
                cache.set(key, value, expire=timeout)
            else:
                cache.set(key, value, expire=Config.CACHE_DEFAULT_TIMEOUT)
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """Delete value from cache"""
        try:
            cache.delete(key)
            return True
        except Exception:
            return False
    
    @staticmethod
    def clear():
        """Clear all cached data"""
        cache.clear()
    
    @staticmethod
    def generate_key(*args, **kwargs) -> str:
        """Generate a cache key from arguments"""
        key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()


def cached(timeout: int = None, key_prefix: str = ""):
    """
    Decorator for caching function results
    Args:
        timeout: Cache timeout in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{key_prefix}:{CacheManager.generate_key(f.__name__, *args, **kwargs)}"
            
            # Try to get from cache
            cached_value = CacheManager.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = f(*args, **kwargs)
            CacheManager.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def invalidate_cache(key_pattern: str):
    """
    Invalidate cache entries matching a pattern
    Args:
        key_pattern: Pattern to match cache keys
    """
    for key in cache:
        if key_pattern in str(key):
            cache.delete(key)


# Specific cache helpers for common operations
def get_user_cache_key(uid: str) -> str:
    """Generate cache key for user data"""
    return f"user:{uid}"


def get_syllabus_cache_key(subject: str, purpose: str) -> str:
    """Generate cache key for syllabus data"""
    return f"syllabus:{purpose}:{subject}"


def get_chapters_cache_key(uid: str) -> str:
    """Generate cache key for user chapters"""
    return f"chapters:{uid}"


def get_ai_risk_cache_key(uid: str) -> str:
    """Generate cache key for AI risk/readiness predictions"""
    return f"gemini_risk:predict_student_risk_and_readiness:{uid}"


def get_ai_cluster_cache_key(class_id: str) -> str:
    """Generate cache key for AI class clustering"""
    return f"gemini_cluster:analyze_class_study_patterns:{class_id}"


def clear_ai_cache_for_student(uid: str):
    """Clear AI cache for a specific student"""
    risk_key = get_ai_risk_cache_key(uid)
    CacheManager.delete(risk_key)
    print(f"Cleared AI risk cache for student {uid}")


def clear_ai_cache_for_class(class_id: str):
    """Clear AI cache for a specific class"""
    cluster_key = get_ai_cluster_cache_key(class_id)
    CacheManager.delete(cluster_key)
    print(f"Cleared AI clustering cache for class {class_id}")


def clear_all_ai_cache():
    """Clear all AI-related cache entries"""
    invalidate_cache("gemini_")
    print("Cleared all AI cache entries")


def clear_cache_for_pattern(pattern: str):
    """Clear cache entries matching a pattern (for testing)"""
    invalidate_cache(pattern)
    print(f"Cleared cache entries matching pattern: {pattern}")


def list_cache_keys(pattern: str = None) -> list:
    """List cache keys, optionally filtered by pattern (for debugging)"""
    keys = list(cache.iterkeys())
    if pattern:
        keys = [key for key in keys if pattern in str(key)]
    return keys
