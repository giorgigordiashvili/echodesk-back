#!/usr/bin/env python3
"""
Direct test of DigitalOcean Spaces upload
Run this on your server to test if credentials and bucket configuration work
"""

import os
import sys
import boto3
from botocore.exceptions import ClientError
from decouple import config

# Load environment variables
DO_SPACES_KEY = config('DO_SPACES_KEY', default='')
DO_SPACES_SECRET = config('DO_SPACES_SECRET_KEY', default='')
DO_SPACES_BUCKET = config('DO_SPACES_BUCKET_NAME', default='echodesk-spaces')
DO_SPACES_ENDPOINT = config('DO_SPACES_ENDPOINT_URL', default='https://fra1.digitaloceanspaces.com')
DO_SPACES_REGION = config('DO_SPACES_REGION', default='fra1')

print("=" * 70)
print("DigitalOcean Spaces Direct Upload Test")
print("=" * 70)

# Display configuration (masked)
print("\n📋 Configuration:")
print(f"  Access Key: {DO_SPACES_KEY[:10]}...{DO_SPACES_KEY[-4:] if len(DO_SPACES_KEY) > 14 else '****'}")
print(f"  Secret Key: {'*' * 10}...{DO_SPACES_SECRET[-4:] if len(DO_SPACES_SECRET) > 4 else '****'}")
print(f"  Bucket: {DO_SPACES_BUCKET}")
print(f"  Endpoint: {DO_SPACES_ENDPOINT}")
print(f"  Region: {DO_SPACES_REGION}")

if not DO_SPACES_KEY or not DO_SPACES_SECRET:
    print("\n❌ ERROR: Missing credentials!")
    print("   Make sure DO_SPACES_KEY and DO_SPACES_SECRET_KEY are set")
    sys.exit(1)

# Create boto3 client
print("\n🔧 Creating boto3 client...")
try:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=DO_SPACES_KEY,
        aws_secret_access_key=DO_SPACES_SECRET,
        endpoint_url=DO_SPACES_ENDPOINT,
        region_name=DO_SPACES_REGION
    )
    print("✅ Client created successfully")
except Exception as e:
    print(f"❌ Failed to create client: {e}")
    sys.exit(1)

# Test 1: List buckets
print("\n📦 Test 1: Listing buckets...")
try:
    response = s3_client.list_buckets()
    print(f"✅ Can list buckets: {[b['Name'] for b in response['Buckets']]}")
except Exception as e:
    print(f"❌ Cannot list buckets: {e}")

# Test 2: Check if bucket exists
print(f"\n🪣 Test 2: Checking if bucket '{DO_SPACES_BUCKET}' exists...")
try:
    s3_client.head_bucket(Bucket=DO_SPACES_BUCKET)
    print(f"✅ Bucket '{DO_SPACES_BUCKET}' exists and is accessible")
except ClientError as e:
    error_code = e.response['Error']['Code']
    print(f"❌ Bucket check failed: {error_code}")
    if error_code == '404':
        print("   Bucket does not exist")
    elif error_code == '403':
        print("   Access denied - check permissions")
    sys.exit(1)

# Test 3: Upload a simple test file - MINIMAL parameters
print("\n📤 Test 3: Uploading test file with MINIMAL parameters...")
test_content = b"Hello from EchoDesk test!"
test_key = "test_upload_simple.txt"

try:
    print(f"   Uploading to: {test_key}")
    print(f"   Parameters: Bucket, Key, Body only")

    s3_client.put_object(
        Bucket=DO_SPACES_BUCKET,
        Key=test_key,
        Body=test_content
    )
    print(f"✅ Upload successful!")

    # Get the URL
    url = f"{DO_SPACES_ENDPOINT.replace('https://', f'https://{DO_SPACES_BUCKET}.')}/{test_key}"
    print(f"   URL: {url}")

    # Clean up
    s3_client.delete_object(Bucket=DO_SPACES_BUCKET, Key=test_key)
    print(f"   Cleaned up test file")

except ClientError as e:
    print(f"❌ Upload failed!")
    print(f"   Error Code: {e.response['Error']['Code']}")
    print(f"   Error Message: {e.response['Error'].get('Message', 'None')}")
    print(f"   Full response: {e.response}")

# Test 4: Upload with ContentType
print("\n📤 Test 4: Uploading test file with ContentType...")
test_key_2 = "test_upload_with_content_type.txt"

try:
    print(f"   Uploading to: {test_key_2}")
    print(f"   Parameters: Bucket, Key, Body, ContentType")

    s3_client.put_object(
        Bucket=DO_SPACES_BUCKET,
        Key=test_key_2,
        Body=test_content,
        ContentType='text/plain'
    )
    print(f"✅ Upload with ContentType successful!")

    # Clean up
    s3_client.delete_object(Bucket=DO_SPACES_BUCKET, Key=test_key_2)
    print(f"   Cleaned up test file")

except ClientError as e:
    print(f"❌ Upload failed!")
    print(f"   Error Code: {e.response['Error']['Code']}")
    print(f"   Error Message: {e.response['Error'].get('Message', 'None')}")
    print(f"   Full response: {e.response}")

# Test 5: Upload with ACL
print("\n📤 Test 5: Uploading test file with ACL='public-read'...")
test_key_3 = "test_upload_with_acl.txt"

try:
    print(f"   Uploading to: {test_key_3}")
    print(f"   Parameters: Bucket, Key, Body, ACL")

    s3_client.put_object(
        Bucket=DO_SPACES_BUCKET,
        Key=test_key_3,
        Body=test_content,
        ACL='public-read'
    )
    print(f"✅ Upload with ACL successful!")

    # Clean up
    s3_client.delete_object(Bucket=DO_SPACES_BUCKET, Key=test_key_3)
    print(f"   Cleaned up test file")

except ClientError as e:
    print(f"❌ Upload with ACL failed!")
    print(f"   Error Code: {e.response['Error']['Code']}")
    print(f"   Error Message: {e.response['Error'].get('Message', 'None')}")
    print(f"   This might be the issue! ACL might not be allowed.")

# Test 6: Upload to media/gallery path
print("\n📤 Test 6: Uploading to media/gallery path...")
test_key_4 = "media/gallery/test/test_upload.txt"

try:
    print(f"   Uploading to: {test_key_4}")
    print(f"   Parameters: Bucket, Key, Body, ContentType")

    s3_client.put_object(
        Bucket=DO_SPACES_BUCKET,
        Key=test_key_4,
        Body=test_content,
        ContentType='text/plain'
    )
    print(f"✅ Upload to nested path successful!")

    # Clean up
    s3_client.delete_object(Bucket=DO_SPACES_BUCKET, Key=test_key_4)
    print(f"   Cleaned up test file")

except ClientError as e:
    print(f"❌ Upload to nested path failed!")
    print(f"   Error Code: {e.response['Error']['Code']}")
    print(f"   Error Message: {e.response['Error'].get('Message', 'None')}")

print("\n" + "=" * 70)
print("Test completed!")
print("=" * 70)
