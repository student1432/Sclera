#!/usr/bin/env python3
"""
Cache Management Testing Script for Sclera Academic

This script demonstrates how to clear AI cache for testing purposes.
Usage examples:
1. Clear cache for a specific class
2. Clear cache for a specific student  
3. Clear all AI cache
4. List current cache entries
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:5000"  # Change if your app runs on different port

def clear_class_ai_cache(class_id, session_cookie):
    """Clear AI cache for a specific class"""
    url = f"{BASE_URL}/api/cache/clear/ai/class/{class_id}"
    headers = {"Content-Type": "application/json"}
    cookies = {"session": session_cookie}
    
    try:
        response = requests.post(url, headers=headers, cookies=cookies)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ {result['message']}")
            return True
        else:
            print(f"✗ Failed to clear class cache: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error clearing class cache: {e}")
        return False

def clear_student_ai_cache(student_uid, session_cookie):
    """Clear AI cache for a specific student"""
    url = f"{BASE_URL}/api/cache/clear/ai/student/{student_uid}"
    headers = {"Content-Type": "application/json"}
    cookies = {"session": session_cookie}
    
    try:
        response = requests.post(url, headers=headers, cookies=cookies)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ {result['message']}")
            return True
        else:
            print(f"✗ Failed to clear student cache: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error clearing student cache: {e}")
        return False

def clear_all_ai_cache(session_cookie):
    """Clear all AI cache entries (admin only)"""
    url = f"{BASE_URL}/api/cache/clear/ai/all"
    headers = {"Content-Type": "application/json"}
    cookies = {"session": session_cookie}
    
    try:
        response = requests.post(url, headers=headers, cookies=cookies)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ {result['message']}")
            return True
        else:
            print(f"✗ Failed to clear all AI cache: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error clearing all AI cache: {e}")
        return False

def list_cache_entries(pattern="", session_cookie=""):
    """List cache entries (admin only)"""
    url = f"{BASE_URL}/api/cache/list"
    params = {"pattern": pattern} if pattern else {}
    cookies = {"session": session_cookie}
    
    try:
        response = requests.get(url, params=params, cookies=cookies)
        if response.status_code == 200:
            result = response.json()
            print(f"Found {result['count']} cache entries:")
            for key in result['keys'][:10]:  # Show first 10
                print(f"  - {key}")
            if result['count'] > 10:
                print(f"  ... and {result['count'] - 10} more")
            return True
        else:
            print(f"✗ Failed to list cache: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error listing cache: {e}")
        return False

def clear_cache_by_pattern(pattern, session_cookie):
    """Clear cache entries matching a pattern (admin only)"""
    url = f"{BASE_URL}/api/cache/clear/pattern"
    headers = {"Content-Type": "application/json"}
    cookies = {"session": session_cookie}
    data = {"pattern": pattern}
    
    try:
        response = requests.post(url, headers=headers, cookies=cookies, json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ {result['message']}")
            return True
        else:
            print(f"✗ Failed to clear cache by pattern: {response.status_code}")
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error clearing cache by pattern: {e}")
        return False

def main():
    """Main testing function"""
    print("=== Sclera Academic Cache Management Testing ===\n")
    
    # You need to provide a valid session cookie from a logged-in teacher/admin
    session_cookie = input("Enter your session cookie (from browser dev tools): ").strip()
    
    if not session_cookie:
        print("Session cookie is required. Please log in and get the session cookie.")
        return
    
    print("\nAvailable operations:")
    print("1. Clear AI cache for a specific class")
    print("2. Clear AI cache for a specific student")
    print("3. Clear all AI cache (admin only)")
    print("4. List cache entries (admin only)")
    print("5. Clear cache by pattern (admin only)")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == "1":
        class_id = input("Enter class ID: ").strip()
        if class_id:
            clear_class_ai_cache(class_id, session_cookie)
    
    elif choice == "2":
        student_uid = input("Enter student UID: ").strip()
        if student_uid:
            clear_student_ai_cache(student_uid, session_cookie)
    
    elif choice == "3":
        confirm = input("Are you sure you want to clear ALL AI cache? (yes/no): ").strip().lower()
        if confirm == "yes":
            clear_all_ai_cache(session_cookie)
    
    elif choice == "4":
        pattern = input("Enter pattern to filter (leave empty for all): ").strip()
        list_cache_entries(pattern, session_cookie)
    
    elif choice == "5":
        pattern = input("Enter pattern to clear: ").strip()
        if pattern:
            clear_cache_by_pattern(pattern, session_cookie)
    
    else:
        print("Invalid choice")

if __name__ == "__main__":
    main()
