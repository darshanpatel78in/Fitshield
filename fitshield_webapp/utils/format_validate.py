
from io import BytesIO
import io
import random
import re
import tempfile
import time
from urllib.parse import urlencode
import uuid
import ffmpeg
import qrcode
import requests
import os
import boto3
import subprocess
from django.http import JsonResponse
from rest_framework.decorators import api_view
import requests
from uuid import uuid4
from django.conf import settings
from config.connection import db
from config.s3_connection import s3_client, bucket_name
from fitshield.settings import AWS_ACCESS_KEY_ID, AWS_S3_REGION, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET
from fitshield_webapp.utils.generate_id import generate_dish_id
from rest_framework import status
from rest_framework.response import Response
from datetime import datetime, timedelta


# def validate_email(email):
#     email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
#     return re.match(email_regex, email) is not None

def validate_email(email):
    # print("not done")
    email_regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
    if re.match(email_regex, email):
        # print("doneee")
        return email
    return None

def validate_phone(phone_number):
    if len(phone_number) != 10 or not phone_number.isdigit():
        return "Phone number must be exactly 10 digits."
    if re.match(r"(\d)\1{9}$", phone_number):
        return "Phone number cannot contain repeated digits (e.g., 1111111111)."
    return None

    
def validate_time_format(time_str):
    try:
        # Support 12-hour time format with AM/PM
        datetime.strptime(time_str, "%I:%M %p")
        return True
    except ValueError:
        return False

def validate_date_format(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d") 
        return True
    except ValueError:
        return False

def validate_social_media(social_media):
    valid_platforms = ['facebook', 'instagram', 'twitter', 'linkedin']
    for platform, url in social_media.items():
        if platform not in valid_platforms:
            return f"Invalid platform {platform}. Valid platforms are {', '.join(valid_platforms)}."
        if not is_valid_url(url):
            return f"Invalid URL for platform {platform}."
    return None

def is_valid_url(url):
    return re.match(r'^(http|https)://', url) is not None

def normalize(text):
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text) 
        text = re.sub(r'\s+', ' ', text)  
        lowercase = text.strip().lower()  
        return lowercase

def normalize_without_spaces(text):
        normalizeword =  normalize(text).replace(' ', '')
        return normalizeword

def normalizarion(dish_name):
    normalized_dish_name = dish_name.replace(" ", "").lower()  
    return normalized_dish_name

def validate_bank_name(bank_name):
    return bool(re.match(r'^[a-zA-Z0-9 .,-]{3,100}$', bank_name))


def validate_upi_id(upi_id):
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z]{3,}$', upi_id))


def parse_percentage(value):
    try:
        if isinstance(value, str) and value.endswith('%'):
            return value    
    except (ValueError, TypeError):
        return None

def validate_taxes(tax_value):
    try:
        # If the value is a string and ends with '%', parse it as a float
        if isinstance(tax_value, str) and tax_value.endswith('%'):
            numeric_value = float(tax_value.strip('%'))  # Convert to float
            if 0 <= numeric_value <= 100:
                return True
            return False
    except (ValueError, TypeError):
        return False

# Generate Thumbnail

# Function to download video using URL
def download_video(video_url, local_path):
    response = requests.get(video_url, stream=True)
    with open(local_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

# Function to extract a thumbnail
def extract_thumbnail(video_path, thumbnail_path, time="00:00:05"):
    ffmpeg_path = r"C:/ffmpeg/bin/ffmpeg.exe" 
    # print(video_path)
    command = [
        ffmpeg_path,
        "-loglevel", "error",
        "-i", video_path,        # Input video
        "-ss", time,             # Time position (5 seconds)
        "-vframes", "1",         # Number of frames
        thumbnail_path           # Output image path
    ]
    # subprocess.run(command, check=True)
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def calculate_profile_progress(restro_id):
    restrodata_collection = db["RestroData"]
    restaurant_data = restrodata_collection.find_one({"_id": restro_id})

    if not restaurant_data:
        return 0  # If no data found, return 0%

    # Define required fields for progress calculation
    required_fields = {
        "name": {"value": restaurant_data.get("name"), "weight": 10},  
        "fassi_id": {"value": restaurant_data.get("fassi_id"), "weight": 10}, 
        "image_url": {
            "value": restaurant_data.get("image_url") or restaurant_data.get("profile_image"),
            "weight": 15
        },
        "personal_details": {
            "value": restaurant_data.get("personal_details") if restaurant_data.get("personal_details") else None,
            "weight": 10
        },
        "bank_details": {"value": restaurant_data.get("bank_details", {}), "weight": 15},  # Bank details are crucial
        "working_hours": {
            "value": restaurant_data.get("working_hours") if restaurant_data.get("working_hours") else None,
            "weight": 10
        }     }


    # Check bank details specifically for service charge logic
    bank_details = required_fields["bank_details"]["value"]
    if bank_details and isinstance(bank_details, dict):
        if bank_details.get("bank_name") and bank_details.get("upi_id"):
            required_fields["bank_details"]["value"] = bank_details
        else:
            # print("Bank Details Missing or Incomplete:", bank_details)
            required_fields["bank_details"]["value"] = None



    # print("Required Fieldsssssssssssssss:", required_fields) 

    # Calculate total possible weight
    total_weight = sum(field["weight"] for field in required_fields.values())

    # Calculate obtained weight based on completed fields
    obtained_weight = sum(field["weight"] for field in required_fields.values() if field["value"])

    # print("Completed Weight:", obtained_weight, "/", total_weight)

    # Base progress is set to 30%
    base_progress = 30

    # Calculate additional progress (remaining 70%)
    additional_progress = round((obtained_weight / total_weight) * 70) if total_weight > 0 else 0

    # Total progress
    return base_progress + additional_progress

# # QR Code - generate content & s3 Path
def generate_qr_code_content(restro_id, table_number, floor_name,force_regenerate= False):
    query_params = {
        "restro_id" : restro_id,
        "table_number": table_number,
        "floor_name" : floor_name,
    }

    qr_url = f"{settings.BASE_URL}?{urlencode(query_params)}"
    qr_img = qrcode.make(qr_url)
    file_obj = BytesIO()
    return file_obj.getvalue()

def upload_to_s3(s3_file_path, file_content):
    try:
        # Debug: Log input type and size
        if isinstance(file_content, BytesIO):
            content_size = file_content.getbuffer().nbytes
            # print("Debug: File content is BytesIO")
        elif isinstance(file_content, bytes):
            content_size = len(file_content)
            file_content = BytesIO(file_content)  # Wrap in BytesIO for upload_fileobj
            # print("Debug: File content is bytes")
        else:
            raise ValueError("Unsupported file content type. Must be bytes or BytesIO.")

        # Upload the file using an in-memory buffer
        s3_client.upload_fileobj(file_content, bucket_name, s3_file_path)
        # print("Debug: S3 upload completed")
        
        # Construct and return the S3 URL
        s3_url = f"https://{bucket_name}.s3.{settings.aws_s3_region}.amazonaws.com/{s3_file_path}"
        # print(f"Debug: Uploaded file URL: {s3_url}")
        return s3_url

    except boto3.exceptions.S3UploadFailedError as e:
        # print(f"Error: S3 upload failed: {str(e)}")
        raise Exception(f"S3 upload failed: {str(e)}")
    except Exception as e:
        # print(f"Error: General exception during S3 upload: {str(e)}")
        raise Exception(f"Failed to upload file to AWS S3: {str(e)}")

def generate_thumbnail_from_video(video_content, time=1):
    try:
        # Create a temporary file for the FFmpeg output
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_output:
            temp_output_path = temp_output.name

        # Run FFmpeg to extract a frame as a thumbnail
        ffmpeg.input("pipe:0", ss=time)\
              .output(temp_output_path, vframes=1, format="image2", vcodec="mjpeg")\
              .run(input=video_content, capture_stdout=True, capture_stderr=True)

        # Load the thumbnail into a BytesIO object
        with open(temp_output_path, "rb") as f:
            thumbnail_content = f.read()

        # Clean up the temporary file
        os.remove(temp_output_path)

        return BytesIO(thumbnail_content)

    except ffmpeg.Error as e:
        raise Exception(f"FFmpeg error: {e.stderr.decode('utf-8')}")
    except Exception as e:
        raise Exception(f"Failed to generate thumbnail: {str(e)}")

def validate_fssai_id(fssai_id):
    if not fssai_id:
        return "FSSAI ID is required."
    
    if not re.match(r'^\d{14}$', fssai_id): 
        return "Invalid FSSAI ID. It must be a 14-digit numeric value."

    return None 

def extract_name_from_email(email):
    if "@" in email:
        local_part = email.split("@")[0]  # Get part before '@'
        name_parts = local_part.split(".")  # Split by '.'
        return " ".join(part.capitalize() for part in name_parts)  # Capitalize each part
    return "User"  

def generate_otp():
    return random.randint(100000, 999999)

def normalize_string(input_string):
    return " ".join(input_string.lower().strip().split())

  
def sanitize_cooking_method(cooking_method):

    if not cooking_method:
        return cooking_method 

    # print(f"Original Cooking Method: {repr(cooking_method)}") 
    
    if not isinstance(cooking_method, str):
        # print(f"Warning: Cooking method is not a string: {repr(cooking_method)}")
        return "" 
    
    if not cooking_method.replace("'", "").replace(" ", "").isalpha():
        # print(f"Warning: Invalid cooking method value detected: {repr(cooking_method)}")
        return "" 

    sanitized_method = cooking_method.replace("'e", "e").replace("’e", "e").replace("`e", "e").replace("é","e")

    # print(f"Sanitized Cooking Method: {repr(sanitized_method)}")  

    return sanitized_method



# Function to validate numeric input and extract quantity
def parse_quantity(input_str, expected_unit):
    match = re.match(r"(\d+(?:\.\d+)?)", input_str.strip())  # Extract number
    if match:
        return float(match.group(1)), expected_unit  # Return number and unit
    else:
        # print("Invalid input! Please enter a valid quantity (e.g., '200').")
        exit()

import datetime

def serialize_datetime(obj):
    if isinstance(obj, dict):
        return {k: serialize_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_datetime(v) for v in obj]
    elif isinstance(obj, datetime.datetime):
        return obj.isoformat()  # Converts datetime to ISO 8601 string
    return obj

# Utility function to round a float to 2 decimal places
def two_decimals(value):
    return float(f"{value:.2f}")


from datetime import datetime, timedelta
import traceback  # Import traceback for detailed error messages

def store_notification(collection, restro_id, notification_type, event, description, details, expiry_hours=None):

    try:
        # print("All data:", restro_id, notification_type, event, description, details, expiry_hours)

        # Ensure event is a valid string
        if not isinstance(event, str):
            raise ValueError("Event must be a string")

        # Generate notification ID
        notification_id = f"{restro_id}_{event.replace(' ', '_')}_{datetime.utcnow().strftime('%H%M%S')}"
        # print("Generated Notification ID:", notification_id)

        # Construct notification document
        notification = {
            "_id": notification_id,
            "type": notification_type,
            "event": event,
            "description": description,
            "details": details,
            "created_at": datetime.utcnow().isoformat(),  
            "updated_at": datetime.utcnow().isoformat()   
        }

        # Add expiry timestamp if needed
        if expiry_hours:
            notification["expires_at"] = (datetime.utcnow() + timedelta(hours=expiry_hours)).isoformat()

        # Check if restaurant exists in MongoDB
        existing_document = collection.find_one({"_id": restro_id})

        if existing_document:
            collection.update_one(
                {"_id": restro_id},
                {"$push": {"notifications": notification}}
            )
        else:
            collection.insert_one({
                "_id": restro_id,
                "notifications": [notification]
            })
        return "Notification stored successfully" 

    except Exception as e:
        return f"Notification failed: {str(e)}"
