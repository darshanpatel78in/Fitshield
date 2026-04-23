import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError
from django.conf import settings

bucket_name = settings.AWS_STORAGE_BUCKET

s3_client = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION,
    )

def get_s3_client():
    return s3_client

def check_s3_connection():
    try:
        s3_client = get_s3_client()  
        response = s3_client.list_buckets()
        bucket_count = len(response.get('Buckets', []))
        return {
            "status": True,
            "message": f"AWS S3 connection successful. Found {bucket_count} bucket(s)."
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"AWS S3 connection error: {str(e)}"
        }
