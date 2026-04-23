from asyncio.log import logger
from datetime import datetime, timedelta, timezone
import logging
from random import randint
import time
from urllib.parse import unquote, urlparse
from django.views.decorators.csrf import csrf_exempt
import phonenumbers
from rest_framework import status
import pytz
from fitshield_webapp.utils.logging_utils import get_logger
from fitshield_webapp.utils.mail import send_admin_email
from ...utils.generate_id import generate_restro_id
from fitshield_webapp.utils.find_address import parse_address
from fitshield_webapp.utils.format_validate import calculate_profile_progress, extract_name_from_email, generate_otp
from fitshield_webapp.utils.otp_helpers import send_otp_via_email, send_otp_via_sms
from fitshield_webapp.utils.serializers import SendOTPSerializer
from rest_framework.decorators import api_view
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response
from geopy.geocoders import Nominatim
from config.s3_connection import s3_client, bucket_name

@api_view(['POST'])
def get_address(request):

    #logger.info("Received request with data: %s", request.data)
    data = request.data
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not latitude or not longitude:
        #logger.warning("Latitude or Longitude is missing in the request.")
        return Response(
            {"error":"Latitude and Longitude are required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        logger.info("Processing location for latitude: %s, longitude: %s", latitude, longitude)
        latitude = float(latitude)
        longitude = float(longitude)

        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            logger.warning("Latitude and Longitude values are out of range. Latitude: %s, Longitude: %s", latitude, longitude)
            return Response(
                {"error": "Latitude and Longitude values are out of range."},
                status=status.HTTP_400_BAD_REQUEST
            )

        #Change in Production
        geolocator = Nominatim(user_agent="fitshield_local/1.0 (s.fitshield@gmail.com)")
        location = geolocator.reverse((latitude, longitude), language='en')

        if location:
            logger.info("Location found: %s", location.address)
            country_code_region  = location.raw.get('address', {}).get('country_code', '').upper()
            country_code = (
                f"+{phonenumbers.country_code_for_region(country_code_region)}"
                if country_code_region else "country code not found"
            )

            logger.info("Country code: %s", country_code)
            address = location.address or "Address not found"

            #seprate address
            detailed_address, city, state, pincode, country = parse_address(address)

            return Response({"country_code": country_code,
                             "detailed_address": detailed_address,
                             "city": city,
                             "state": state,
                             "pincode": pincode,
                             "country": country})

        logger.warning("Location not found for the given latitude and longitude.")
        return Response(
            {"error": "Location not found", "details": "Invalid latitude or longitude."},
            status=status.HTTP_404_NOT_FOUND
        )
    except ValueError:
        logger.error("Invalid latitude or longitude format.")
        return Response(
            {"error": "Invalid latitude or longitude format."},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e))
        return Response(
           {"error": "An unexpected error occurred", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def owner_exists(request):
    logger.info("Received owner_exists request: %s", request.data)

    serializer = SendOTPSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning("Invalid data received: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    country_code = validated_data.get("country_code", "").strip()  # Remove leading/trailing spaces
    phone_number = validated_data.get("phone_number", "").strip()
    email = validated_data.get("email", "").strip()

    logger.info(
        "Valid data: country_code=%s, phone_number=%s, email=%s",
        country_code, phone_number, email
    )

    try:
        restrodata_collection = db["RestroData"]
        is_exist = False
        restro_id = None  # Initialize restro_id to avoid reference errors

        if not phone_number and not email:
            logger.warning("Neither phone_number nor email provided.")
            return Response(
                {"error": "Either phone_number or email must be provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check phone_number
        if phone_number:
            logger.info("Checking phone number in the database: %s", phone_number)
            document = restrodata_collection.find_one({
                "country_code": country_code,
                "phone_number": phone_number
            })
            if document:
                is_exist = True
                restro_id = document.get("_id")
                logger.info("Phone number found in the database. Restro ID: %s", restro_id)

        # If phone_number not found, check email
        if email and not is_exist:
            logger.info("Checking email in the database: %s", email)
            document = restrodata_collection.find_one({"email": email})
            if document:
                is_exist = True
                restro_id = document.get("_id")
                logger.info("Email found in the database. Restro ID: %s", restro_id)

        logger.info("checking Owner existence result: %s", is_exist)

        # Handle the case if restro_id is found
        if restro_id:
            # For example, return a message or additional details
            return Response(
                {
                    "is_exist": True,
                    "restro_id": str(restro_id),
                    "message": "Owner already exists in the database."
                },
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {
                    "is_exist": False,
                    "restro_id": "",
                    "message": "Owner does not exist in the database."
                },
                status=status.HTTP_200_OK
            )

    except Exception as e:
        logger.error("An unexpected error occurred: %s", str(e), exc_info=True)
        return Response(
            {"error": "An unexpected error occurred", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def send_otp(request):
    logger.info("Received send_otp request: %s", request.data)
    otp_store = {}
    # Serialize data
    serializer = SendOTPSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning("Invalid data received: %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    country_code = validated_data.get("country_code", "").strip()
    phone_number = validated_data.get("phone_number", "").strip()
    email = validated_data.get("email", "").strip()
    # user_name = request.POST.get("user_name", "User") 

    logger.info("Valid data: country_code=%s, phone_number=%s, email=%s", country_code, phone_number, email)

    if not phone_number and not email:
        logger.warning("Neither phone_number nor email provided.")
        return Response(
            {"error": "Either Phone Number or Email must be Provided."},
            status=status.HTTP_400_BAD_REQUEST
        )
    otp = generate_otp()

    if phone_number:
        phone = f"{country_code.strip('+')}{phone_number.strip()}"

        try:
            phone_int = int(phone)
        except ValueError:
            return JsonResponse({'error': 'Invalid phone number format.'}, status=400)

        otp_store[phone] = {'otp': otp, 'expires_at': datetime.utcnow() + timedelta(minutes=2)}

        instance_id = "679DF139A477D"
        access_token = "679ded35dde2c"

        success, message = send_otp_via_sms(phone_int, otp, instance_id, access_token)

    elif email:
        logger.info("Sending OTP via email to %s", email)
        user = extract_name_from_email(email)  
        success, message = send_otp_via_email(user,email, otp)

    else:
        success = False
        message = "Failed to determine the recipient for OTP."
        logger.error("Failed to determine recipient for OTP.")

    if success:
        logger.info("OTP Sent Successfully.")
        return Response(
            {
                "message": message,
                "otp": str(otp)
            },
            status=status.HTTP_200_OK
        )
    else:
        logger.error("Failed to send OTP: %s", message)
        return Response({"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(['POST'])
def upload_menu(request):
    try:
        # logger.info("Received request to upload menu for restaurant ID: %s", request.data.get("restro_id"))

        restro_id = request.data.get("restro_id")
        logger = get_logger(restro_id,"success")
        logger.info("Starting to upload images...")

        uploaded_files = request.FILES.getlist("files")

        if not restro_id or not uploaded_files:
            logger.error("Missing required data: restro_id or uploaded_files")
            return Response(
                {"error": "Restaurant ID, image are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info("Looking for restaurant with restro_id: %s", restro_id)
        restrodata_collection = db["RestroData"]
        restaurant = restrodata_collection.find_one({"_id": restro_id})
        restaurant_name = restaurant.get("name")

        if not restaurant:
            logger.error("Restaurant not found for restro_id: %s", restro_id)
            return Response(
                {"error": "Restaurant not found with the provided ID."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Set default progress to 30% if the profile is new
        if not restaurant.get("profile_progress"):
            logger.info("Setting default profile progress to 30% for restro_id: %s", restro_id)
            restrodata_collection.update_one(
                {"_id": restro_id},
                {"$set": {"profile_progress": 30}}
            )

        existing_image_urls = restaurant.get("image_urls", [])
        image_urls = existing_image_urls.copy()
        logger.info("Starting to upload images for restaurant ID: %s", restro_id)

        for uploaded_image in uploaded_files:
            file_name = uploaded_image.name
            file_extension = file_name.split('.')[-1].lower()

            # Validate file type
            if file_extension not in ["jpg", "jpeg", "png", "pdf"]:
                logger.info("Validating file type for image: %s", file_name)
                return Response(
                    {"error": f"Unsupported file type for {file_name}. Only JPG, JPEG, and PNG are allowed."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if any(existing_url.endswith(file_name) for existing_url in image_urls):
                logger.info("Image %s already exists in the restaurant's images. Skipping upload.", file_name)
                continue

            # Generate the S3 path for the image
            s3_path = f"restaurants/{restro_id}/Menu/{file_name}"

            # Change S3 Client
            logger.info("Uploading image to S3: %s", s3_path)
            s3_client.upload_fileobj(uploaded_image, bucket_name, s3_path)
            
            # Generate the public URL for the image
            image_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"
            image_urls.append(image_url)

        # Update MongoDB with the image URL
        logger.info("Updating restaurant record with new image URLs")
        update_data = {
            "image_urls": image_urls,
            "updated_at": datetime.utcnow().isoformat()# Store timestamp in IST
        }
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": update_data}
        )

        logger.info("Successfully uploaded images and updated restaurant record for restro_id: %s", restro_id)

        # Recalculate and update profile progress
        logger.info("Recalculating profile progress for restro_id: %s", restro_id)
        progress = calculate_profile_progress(restro_id)
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": {"profile_progress": str(30)}}
            # {"$set": {"profile_progress": str(progress)}}

        )

        # Fetch the updated record
        updated_restaurant = restrodata_collection.find_one({"_id": restro_id})
        updated_restaurant["_id"] = str(updated_restaurant["_id"])

        if updated_restaurant:
            send_admin_email(
                issue_type="Restaurant Onboard",
                restaurant_name=restaurant_name,
                restro_id=restro_id,
                description="A new Restaurant has onboard"
            )
        # Return success response
        return Response(
            {
                "message": "Image uploaded successfully.",
                "restaurant": updated_restaurant,
                "progress": str(progress),
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        restro_id = request.data.get("restro_id")
        logger = get_logger(restro_id,"error")
        return Response(
            {"error": "An unexpected error occurred.", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    

@csrf_exempt
@api_view(['DELETE'])
def delete_menu(request):
    try:
        file_name = request.data.get('file_name')  
        restro_id = request.data.get('restro_id') 

        if not file_name or not restro_id:
            return JsonResponse({'error': 'File name and restroid are required.'}, status=400)

         # Normalize file_name to handle URL encoding issues
        normalized_file_name = unquote(file_name.strip())

        # Extract the relative key from the full URL
        parsed_url = urlparse(normalized_file_name)
        file_key = parsed_url.path.lstrip('/')  # Remove leading slash
        
        bucket_name = 'fitshield-data'

        folder_path = f"restaurants/{restro_id}/Menu/"
        file_key = f"{folder_path}{file_name}"

        s3_client.delete_object(Bucket=bucket_name, Key=file_key)

        image_urls= f"https://{bucket_name}.s3.amazonaws.com/{file_key}"


        # Delete file entry from MongoDB
        restro_collection = db["RestroData"]
        result = restro_collection.update_one(
            {"restroid": restro_id},
            {"$pull": {"image_urls": f"https://{bucket_name}.s3.amazonaws.com/{file_key}"}}
        )

        if result.modified_count == 0:
            return JsonResponse({'error': 'File entry not found in MongoDB.'}, status=404)


        return JsonResponse({'message': f'File {file_name} deleted successfully.'}, status=200)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@api_view(["POST"])
def restaurant_details(request):
    try:
        # Define required fields
        required_fields = [
            "rest_name", "rest_address", "rest_city", "rest_state", "rest_pincode",
            "country_code", "phone_number", "email", "otp", "is_email_verified", "is_phone_verified"
        ]
        # Check for missing fields
        missing_fields = [field for field in required_fields if field not in request.data]
        if missing_fields:
            return JsonResponse(
                {"message": f"Missing required fields: {', '.join(missing_fields)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        logger.info("Received restaurant details request: %s", request.data)

        # Extract and validate input data
        data = request.data
        name = data["rest_name"]
        pincode = data["rest_pincode"]
        restrodata_collection = db["RestroData"]

        # Check for existing restaurant with the same name and pincode
        existing_restaurant = restrodata_collection.find_one({"name": name, "pincode": pincode})
        if existing_restaurant:
            return JsonResponse(
                {
                    "message": "Restaurant with the same name and pincode already exists in this city.",
                    "restro_id": str(existing_restaurant["_id"])
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate unique restro_id
        restro_id = generate_restro_id(name, pincode)
        logger.info("Generated restro_id: %s", restro_id)

        # Prepare structured data for insertion
        current_time = datetime.utcnow().isoformat()
        
        structured_data = {
            "_id": restro_id,
            "name": name,
            "address": data["rest_address"],
            "city": data["rest_city"],
            "state": data["rest_state"],
            "pincode": pincode,
            "country_code": data["country_code"],
            "phone_number": data["phone_number"],
            "email": data["email"],
            "is_email_verified": data["is_email_verified"],
            "is_phone_verified": data["is_phone_verified"],
            "latitude": data.get("latitude",None),
            "longitude": data.get("longitude",None),
            "is_menu_prepared": data.get("is_menu_prepared", False),
            "created_at": current_time,  # Store time in IST
            "updated_at": current_time
        }

        # Insert data into the database
        result = restrodata_collection.insert_one(structured_data)
        if not result.acknowledged:
            raise Exception("Failed to insert restaurant data into the database.")

        logger.info("Restaurant data inserted successfully with restro_id: %s", restro_id)

        # Prepare response
        response_data = {
            "message": "Restaurant registered successfully.",
            "restaurant": structured_data
        }
        return JsonResponse(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error("Error while registering restaurant: %s", str(e))
        return JsonResponse({"error": "An error occurred while registering the restaurant."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        