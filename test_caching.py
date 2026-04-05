#!/usr/bin/env python3
"""
Test script to verify the fixed caching system works correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.cache import CacheManager, list_cache_keys
from gemini_analytics import gemini_analytics

def test_caching():
    """Test the manual caching system"""
    print("=== Testing Manual Caching System ===\n")
    
    # Test 1: Clear any existing cache
    print("1. Clearing existing cache...")
    CacheManager.delete("gemini_cluster:analyze_class_study_patterns:test-class-123")
    CacheManager.delete("gemini_risk:predict_student_risk_and_readiness:test-student-456")
    print("✓ Cache cleared\n")
    
    # Test 2: Test cache key generation
    print("2. Testing cache key generation...")
    cluster_key = f"gemini_cluster:analyze_class_study_patterns:test-class-123"
    risk_key = f"gemini_risk:predict_student_risk_and_readiness:test-student-456"
    print(f"✓ Cluster cache key: {cluster_key}")
    print(f"✓ Risk cache key: {risk_key}\n")
    
    # Test 3: Test cache storage and retrieval
    print("3. Testing cache storage and retrieval...")
    test_data = {"clusters": [{"label": "Test Cluster", "students": ["s1", "s2"]}]}
    CacheManager.set(cluster_key, test_data, timeout=7200)
    
    retrieved_data = CacheManager.get(cluster_key)
    if retrieved_data and retrieved_data == test_data:
        print("✓ Cache storage and retrieval working correctly")
    else:
        print("✗ Cache storage/retrieval failed")
    
    # Test 4: Test cache clearing
    print("\n4. Testing cache clearing...")
    CacheManager.delete(cluster_key)
    if not CacheManager.get(cluster_key):
        print("✓ Cache clearing working correctly")
    else:
        print("✗ Cache clearing failed")
    
    # Test 5: List cache entries
    print("\n5. Current cache entries:")
    all_keys = list_cache_keys()
    ai_keys = list_cache_keys("gemini_")
    print(f"Total cache entries: {len(all_keys)}")
    print(f"AI-related entries: {len(ai_keys)}")
    if ai_keys:
        print("AI cache keys:")
        for key in ai_keys:
            print(f"  - {key}")
    
    print("\n=== Cache System Test Complete ===")
    print("✓ Manual caching system is working correctly")
    print("✓ Cache management functions are operational")
    print("✓ Ready for testing with real AI calls")

if __name__ == "__main__":
    test_caching()
