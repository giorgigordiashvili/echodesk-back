#!/usr/bin/env python3
"""
Debug script to test S3 upload with content type
Run this on your server to verify the upload fix is working
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'amanati_crm.settings')
django.setup()

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image

def create_test_image():
    """Create a simple test image in memory"""
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes.read()

def test_direct_upload():
    """Test uploading with SimpleUploadedFile (mimics Django request.FILES)"""
    print("\n=== Testing Direct Upload (Correct Method) ===")

    image_data = create_test_image()
    image_file = SimpleUploadedFile(
        "test_image.png",
        image_data,
        content_type="image/png"
    )

    print(f"Image file type: {type(image_file)}")
    print(f"Image file content_type: {image_file.content_type}")
    print(f"Image file name: {image_file.name}")

    try:
        filename = f'test_uploads/direct_test.png'
        path = default_storage.save(filename, image_file)
        url = default_storage.url(path)
        print(f"✅ SUCCESS - Direct upload worked!")
        print(f"   Path: {path}")
        print(f"   URL: {url}")

        # Clean up
        default_storage.delete(path)
        print(f"   Cleaned up test file")
        return True
    except Exception as e:
        print(f"❌ FAILED - Direct upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_contentfile_upload():
    """Test uploading with ContentFile (Wrong Method - loses content_type)"""
    print("\n=== Testing ContentFile Upload (Wrong Method) ===")

    image_data = create_test_image()
    content_file = ContentFile(image_data)

    print(f"ContentFile type: {type(content_file)}")
    print(f"ContentFile has content_type: {hasattr(content_file, 'content_type')}")

    try:
        filename = f'test_uploads/contentfile_test.png'
        path = default_storage.save(filename, content_file)
        url = default_storage.url(path)
        print(f"⚠️  ContentFile upload succeeded (but may have wrong content-type)")
        print(f"   Path: {path}")
        print(f"   URL: {url}")

        # Clean up
        default_storage.delete(path)
        print(f"   Cleaned up test file")
        return True
    except Exception as e:
        print(f"❌ FAILED - ContentFile upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_storage_config():
    """Check storage configuration"""
    print("\n=== Storage Configuration ===")
    from django.conf import settings

    print(f"Storage backend: {settings.DEFAULT_FILE_STORAGE}")
    print(f"AWS Bucket: {settings.AWS_STORAGE_BUCKET_NAME}")
    print(f"AWS Region: {settings.AWS_S3_REGION_NAME}")
    print(f"AWS Endpoint: {settings.AWS_S3_ENDPOINT_URL}")
    print(f"AWS Object Parameters: {settings.AWS_S3_OBJECT_PARAMETERS}")

    # Check if ACL might be causing issues
    if hasattr(settings, 'AWS_DEFAULT_ACL'):
        print(f"AWS Default ACL: {settings.AWS_DEFAULT_ACL}")

def check_view_code():
    """Check if the view has the correct code"""
    print("\n=== Checking View Code ===")

    import tenants.views
    import inspect

    source = inspect.getsource(tenants.views.upload_image)

    if 'ContentFile' in source and 'image_file.read()' in source:
        print("❌ WARNING: View code still uses ContentFile - FIX NOT APPLIED!")
        print("   The server code needs to be updated.")
    elif 'default_storage.save(filename, image_file)' in source:
        print("✅ View code is correct - uses direct image_file")
    else:
        print("⚠️  Cannot determine - check manually")

    print("\nRelevant code snippet:")
    lines = source.split('\n')
    for i, line in enumerate(lines):
        if 'default_storage.save' in line:
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            for j in range(start, end):
                print(f"   {lines[j]}")
            break

if __name__ == '__main__':
    print("=" * 60)
    print("S3 Upload Debug Script")
    print("=" * 60)

    check_storage_config()
    check_view_code()

    success = test_direct_upload()
    test_contentfile_upload()

    print("\n" + "=" * 60)
    if success:
        print("✅ Direct upload works! The fix should be working.")
        print("   If uploads still fail, check:")
        print("   1. Is the Django server restarted?")
        print("   2. Are there multiple Django processes running?")
        print("   3. Check nginx/gunicorn is routing to the correct process")
    else:
        print("❌ Direct upload failed. Check:")
        print("   1. AWS credentials")
        print("   2. S3 bucket permissions")
        print("   3. Network connectivity to S3")
    print("=" * 60)
