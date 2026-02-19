#!/usr/bin/env python3
"""
Simple test script to verify the docs API endpoints work
"""

import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_create_document():
    """Test creating a document"""
    url = f"{BASE_URL}/api/documents"
    data = {
        "title": "Test Document",
        "content": "<p>This is a test document</p>"
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"Create Document Status: {response.status_code}")
        if response.status_code == 201:
            result = response.json()
            print(f"Created document: {result['document']['title']}")
            return result['document']['id']
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_create_folder():
    """Test creating a folder"""
    url = f"{BASE_URL}/api/folders"
    data = {
        "name": "Test Folder"
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"Create Folder Status: {response.status_code}")
        if response.status_code == 201:
            result = response.json()
            print(f"Created folder: {result['folder']['name']}")
            return result['folder']['id']
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_get_documents():
    """Test getting documents"""
    url = f"{BASE_URL}/api/documents"
    
    try:
        response = requests.get(url)
        print(f"Get Documents Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Found {len(result['documents'])} documents")
            return result['documents']
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def test_get_folders():
    """Test getting folders"""
    url = f"{BASE_URL}/api/folders"
    
    try:
        response = requests.get(url)
        print(f"Get Folders Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Found {len(result['folders'])} folders")
            return result['folders']
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

if __name__ == "__main__":
    print("Testing Sclera Docs API...")
    print("=" * 40)
    
    # Test creating a folder
    folder_id = test_create_folder()
    print()
    
    # Test creating a document
    doc_id = test_create_document()
    print()
    
    # Test getting folders
    test_get_folders()
    print()
    
    # Test getting documents
    test_get_documents()
    print()
    
    print("API tests completed!")
