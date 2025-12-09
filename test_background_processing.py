"""
Test script for background processing with Celery

This script tests the background processing setup by:
1. Creating a test job
2. Queuing it for processing
3. Monitoring progress
4. Displaying results

Usage:
    python test_background_processing.py

Prerequisites:
    - Redis running: redis-cli ping
    - Celery worker running: celery -A creatorscribe worker --loglevel=info
    - Django server running: python manage.py runserver
"""

import os
import sys
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'creatorscribe.settings')
django.setup()

from creatorscribe_api.models import Job, Client, User
from creatorscribe_api.tasks import process_content_generation_task
from django.utils import timezone


def test_background_processing():
    """Test the background processing system"""
    
    print("=" * 60)
    print("🧪 Testing Background Processing with Celery")
    print("=" * 60)
    print()
    
    # Check if we have required files
    test_files = ['sample.mp3', 'sample.png']
    available_file = None
    
    for test_file in test_files:
        if os.path.exists(test_file):
            available_file = test_file
            break
    
    if not available_file:
        print("❌ No test files found (sample.mp3 or sample.png)")
        print("Please add a test file to the project root")
        return
    
    print(f"✅ Found test file: {available_file}")
    print()
    
    # Get or create test user and client
    try:
        user = User.objects.first()
        if not user:
            print("❌ No users found. Please create a user first.")
            return
        
        print(f"✅ Using user: {user.email}")
        
        client = Client.objects.filter(user=user).first()
        if not client:
            print("❌ No clients found. Please create a client first.")
            return
        
        print(f"✅ Using client: {client.client_name}")
        print()
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return
    
    # Determine file type
    file_type = 'audio' if available_file.endswith('.mp3') else 'image'
    
    print("=" * 60)
    print("Testing Two-Step Process:")
    print("  Step 1: Create job (uploaded status)")
    print("  Step 2: Queue task for processing")
    print("=" * 60)
    print()
    
    # Step 1: Create a test job in 'uploaded' state
    print("📝 Step 1: Creating test job (uploaded state)...")
    job = Job.objects.create(
        client=client,
        user=user,
        file_type=file_type,
        original_filename=available_file,
        file_path=os.path.abspath(available_file),
        caption_length='medium',
        description_length='medium',
        hashtag_count=15,
        status='uploaded'  # New two-step process: start as 'uploaded'
    )
    
    print(f"✅ Job created: {job.job_id}")
    print(f"   Status: {job.status} (file uploaded, ready for processing)")
    print()
    
    print("User can now configure settings in UI...")
    print()
    
    # Step 2: Update config and queue the task
    print("📝 Step 2: Starting content generation...")
    job.caption_length = 'long'
    job.description_length = 'medium'
    job.hashtag_count = 20
    job.status = 'pending'
    job.save(update_fields=['caption_length', 'description_length', 'hashtag_count', 'status'])
    print(f"   Updated configuration: caption=long, description=medium, hashtags=20")
    print()
    
    # Queue the task
    print("🚀 Queuing task for background processing...")
    task = process_content_generation_task.delay(str(job.job_id))
    print(f"✅ Task queued with ID: {task.id}")
    print()
    
    # Monitor progress
    print("📊 Monitoring progress (polling every 2 seconds)...")
    print("-" * 60)
    
    last_progress = -1
    start_time = time.time()
    
    while True:
        # Refresh job from database
        job.refresh_from_db()
        
        # Only print if progress changed
        if job.progress != last_progress:
            elapsed = int(time.time() - start_time)
            progress_bar = "█" * (job.progress // 5) + "░" * (20 - job.progress // 5)
            print(f"[{elapsed:3d}s] {progress_bar} {job.progress:3d}% | Status: {job.status}")
            last_progress = job.progress
        
        # Check if completed or failed
        if job.status == 'completed':
            print("-" * 60)
            print()
            print("✅ Processing completed successfully!")
            print()
            print("📄 Results:")
            print("-" * 60)
            
            if job.result_data:
                result = job.result_data
                
                print("\n🎯 Caption:")
                print(f"  {result.get('caption', 'N/A')}")
                
                print("\n📝 Description:")
                desc = result.get('description', 'N/A')
                for line in desc.split('\n'):
                    print(f"  {line}")
                
                print("\n🏷️  Hashtags:")
                print(f"  {result.get('hashtags', 'N/A')}")
                
                print()
                print("-" * 60)
                print(f"⏱️  Processing time: {job.get_duration_display()}")
                print(f"📊 Total elapsed: {int(time.time() - start_time)}s")
            
            break
        
        elif job.status == 'failed':
            print("-" * 60)
            print()
            print(f"❌ Processing failed: {job.error_message}")
            break
        
        # Wait before next poll
        time.sleep(2)
    
    print()
    print("=" * 60)
    print("✅ Test completed!")
    print("=" * 60)
    print()
    print("💡 Next steps:")
    print("  1. Implement frontend polling using the examples in frontend_examples/")
    print("  2. Check QUICK_START.md for integration guide")
    print("  3. See CELERY_SETUP.md for production deployment")
    print()


if __name__ == '__main__':
    try:
        test_background_processing()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
