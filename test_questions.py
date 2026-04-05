#!/usr/bin/env python3
"""
Test script to verify seed questions are working correctly
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from test_system import test_system
from templates.academic_data import get_syllabus

def test_seed_questions():
    print("=== Testing Seed Questions ===")
    
    # Test 1: Check if questions exist in database
    print("\n1. Checking questions in database...")
    all_counts = test_system.get_all_question_counts()
    print(f"Total topics with questions: {len(all_counts)}")
    
    if all_counts:
        print("Sample topic counts:")
        for i, (topic_id, counts) in enumerate(list(all_counts.items())[:5]):
            print(f"  {topic_id}: {counts}")
    else:
        print("❌ No questions found in database!")
        return False
    
    # Test 2: Check if we can retrieve questions for a topic
    print("\n2. Testing question retrieval...")
    test_topic_id = list(all_counts.keys())[0] if all_counts else None
    if test_topic_id:
        questions = test_system.get_questions_for_topic(test_topic_id, num_questions=3)
        print(f"Retrieved {len(questions)} questions for topic: {test_topic_id}")
        if questions:
            print(f"Sample question: {questions[0]['text'][:50]}...")
        else:
            print("❌ Failed to retrieve questions!")
            return False
    
    # Test 3: Check syllabus structure
    print("\n3. Checking syllabus structure...")
    syllabus = get_syllabus('school', 'cbse', '9')
    if syllabus:
        print(f"Found {len(syllabus)} subjects for CBSE Grade 9")
        for subj_name, subj_data in list(syllabus.items())[:2]:
            chapters = subj_data.get('chapters', {})
            print(f"  {subj_name}: {len(chapters)} chapters")
            for chap_name, chap_data in list(chapters.items())[:2]:
                topics = chap_data.get('topics', [])
                print(f"    {chap_name}: {len(topics)} topics")
                if topics:
                    topic_name = topics[0].get('name', 'Unknown')
                    print(f"      Sample topic: {topic_name}")
    else:
        print("❌ No syllabus found!")
        return False
    
    # Test 4: Test topic ID generation
    print("\n4. Testing topic ID generation...")
    if syllabus and 'Mathematics' in syllabus:
        math_chapters = syllabus['Mathematics'].get('chapters', {})
        if math_chapters:
            first_chapter = list(math_chapters.keys())[0]
            first_topics = math_chapters[first_chapter].get('topics', [])
            if first_topics:
                topic_name = first_topics[0].get('name', '')
                generated_id = test_system.make_topic_id('cbse', '9', 'Mathematics', first_chapter, topic_name)
                print(f"Generated topic ID: {generated_id}")
                
                # Check if this topic has questions
                if generated_id in all_counts:
                    print(f"✅ Questions found for generated topic ID: {all_counts[generated_id]}")
                else:
                    print(f"❌ No questions found for generated topic ID: {generated_id}")
    
    print("\n=== Test Complete ===")
    return True

if __name__ == "__main__":
    test_seed_questions()
