from datetime import datetime, timedelta, timezone
import json
import logging
from logging.handlers import RotatingFileHandler
import uuid

from fitshield_webapp.utils.format_validate import calculate_profile_progress, parse_percentage, store_notification, validate_bank_name, validate_date_format, validate_email, validate_fssai_id, validate_phone, validate_social_media, validate_time_format, validate_upi_id
from ...utils.logging_utils import get_logger
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response
from rest_framework import status
from config.s3_connection import s3_client, bucket_name
import pytz
from dateutil import parser

def is_24_hours_passed(created_at_str):
    # Convert created_at_str to datetime object
    created_at = datetime.fromisoformat(created_at_str)
    
    # Get current UTC time
    current_utc_time = datetime.utcnow()


    # Check if 24 hours have passed
    return current_utc_time >= created_at + timedelta(hours=24)

                                                     
# Restaurant Details and Management
@api_view(["GET"])
def get_restaurant_details(request):
    try:
        # Extract restaurant ID from query parameters
        restro_id = request.query_params.get("restro_id",)

        # MongoDB collection
        restrodata_collection = db["RestroData"]

        if not restro_id or restro_id == "default_restro":
            return JsonResponse(
                {"error": "Missing required query parameter: 'restro_id'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fetch restaurant document from MongoDB
        restaurant = restrodata_collection.find_one({"_id": restro_id})

        if not restaurant:
            return JsonResponse(
                {"message": "Restaurant not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if 24 hours have passed since creation
        if "created_at" in restaurant:
            created_at_str = restaurant["created_at"]

            if isinstance(created_at_str, str) and is_24_hours_passed(created_at_str):  # Compare strings directly
                restrodata_collection.update_one(
                    {"_id": restro_id},
                    {"$set": {"is_menu_prepared": True}}
                )
                restaurant["is_menu_prepared"] = True

        # Calculate total tables from floor details
        floor_details = restaurant.get("floor_detail", [])
        total_tables = sum(floor.get("number_of_tables", 0) for floor in floor_details)

        # Add total tables to the restaurant details
        restaurant["total_tables"] = total_tables

        return JsonResponse(
            {
                "message": "Restaurant details retrieved successfully.",
                "restaurant": restaurant
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return JsonResponse(
            {"error": "An error occurred while retrieving the restaurant details."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
 
@csrf_exempt
def update_restaurant_details(request):
    try:
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid HTTP method'}, status=405)
        
        MAX_FILE_SIZE_MB = 5  
        if request.content_type.startswith('multipart/form-data'):
            data = request.POST.dict()  # Extract form data as a dictionary
            uploaded_image = request.FILES.get('file')  # Extract file from form
            profile_image = request.FILES.get('profile_image')  # Extract file for profile image

        else:
            data = json.loads(request.body)  # Handle JSON payloads

        def normalize_percentage(value):
            """
            Converts a percentage string to a standardized format with two decimal places.
            Example: '2%' -> '2.00%', '2.5%' -> '2.50%'
            """
            if isinstance(value, str) and value.endswith('%'):
                try:
                    # Remove '%' and format the value to two decimal places
                    numeric_value = float(value.strip('%'))
                    return f"{numeric_value:.2f}%"
                except ValueError:
                    return None
            return value  # Return as-is if not a percentage string

        # data = json.loads(request.body)
        # logger.debug(f"Request data: {data}")
        restro_id = data.get('restro_id')
        restaurant_name = data.get('name')
        fassi_id = data.get('fassi_id')
        uploaded_image = request.FILES.get("file")
        personal_details = data.get('personal_details')
        social_media = data.get('social_media', {})
        bank_details = data.get('bank_details', {})
        working_hours = data.get('working_hours', {})
        special_dates = data.get('special_dates', [])
        profile_image = request.FILES.get("profile_image")


        if not restro_id:
            return JsonResponse({'error': 'restro_id is required'}, status=400)

        restrodata_collection = db["RestroData"]
        restaurant = restrodata_collection.find_one({'_id': restro_id})
        if not restaurant:
            return JsonResponse({'error': 'Restaurant not found'}, status=404)

        update_fields = {}
        errors = []

        # Update restaurant details
        if 'name' in data:
            update_fields['name'] = data['name']

        if 'fassi_id' in data:
            fassi_error = validate_fssai_id(data['fassi_id'])
            if fassi_error:
                errors.append(fassi_error)
            else:
                update_fields['fassi_id'] = data['fassi_id']

        # Update image URL
        if uploaded_image:
            file_name = uploaded_image.name
            file_extension = file_name.split('.')[-1].lower()

            # Validate file type
            if file_extension not in ["jpg", "jpeg", "png"]:
                return Response(
                    {"error": f"Unsupported file type for {file_name}. Only JPG, JPEG, and PNG are allowed."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Generate the S3 path for the image
            s3_path = f"restaurants/{restro_id}/Menu/{file_name}"

            s3_client.upload_fileobj(uploaded_image, bucket_name, s3_path)

            # Generate the public URL for the image
            image_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"

            # Update MongoDB with the image URL

            update_fields['image_url'] = image_url

        # Handle profile image upload
        if profile_image:
            if profile_image.size > MAX_FILE_SIZE_MB * 1024 * 1024:
                return JsonResponse(
                    {"error": f"File size for {profile_image.name} exceeds the {MAX_FILE_SIZE_MB} MB limit."},
                    status=400
                )

            file_name = profile_image.name
            file_extension = file_name.split('.')[-1].lower()

            # Validate file type
            if file_extension not in ["jpg", "jpeg", "png"]:
                return JsonResponse(
                    {"error": f"Unsupported file type for {file_name}. Only JPG, JPEG, and PNG are allowed."},
                    status=400
                )

            # If there's an existing profile image, delete it from S3
            if 'profile_image' in restaurant:
                old_profile_image_url = restaurant['profile_image']
                old_s3_path = old_profile_image_url.replace(f"https://{bucket_name}.s3.amazonaws.com/", "")

                try:
                    # Delete old profile image from S3
                    s3_client.delete_object(Bucket=bucket_name, Key=old_s3_path)
                    # print(f"Deleted old profile image: {old_s3_path}")
                except Exception as e:
                    return JsonResponse({"error": f"Failed to delete old profile image: {str(e)}"}, status=500)

            # Generate a unique S3 path for the new profile image
            unique_file_name = f"{uuid.uuid4()}_{file_name}"
            s3_path = f"restaurants/{restro_id}/profile/{unique_file_name}"

            # Upload the new profile image to S3
            s3_client.upload_fileobj(profile_image, bucket_name, s3_path)

            # Generate the public URL for the new profile image
            profile_image_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"

            # Update the database with the new profile image URL
            update_fields['profile_image'] = profile_image_url

        # Validate personal details
        if personal_details:
            phone_error = validate_phone(personal_details.get('phone_number', ''))
            if phone_error:
                errors.append(phone_error)

            email = personal_details.get('email', '')
            if email:
                validated_email = validate_email(email)
                if validated_email:
                    update_fields['personal_details.email'] = validated_email
                else:
                    errors.append("Invalid email")

            # Update other personal details fields
            for key in ['user_name', 'role', 'phone_number']:  # Removed 'email' from here
                if key in personal_details:
                    update_fields[f"personal_details.{key}"] = personal_details[key]

        # Ensure we do not overwrite the top-level email
        if 'email' in update_fields:
            del update_fields['email']

        # Validate social media
        if social_media:
            social_error = validate_social_media(social_media)
            if social_error:
                errors.append(social_error)
            else:
                update_fields['social_media'] = social_media

        # Validate bank details
        if bank_details:
            bank_name = bank_details.get('bank_name')
            if bank_name and not validate_bank_name(bank_name):
                errors.append('Invalid Bank Name')

            upi_id = bank_details.get('upi_id')
            if upi_id and not validate_upi_id(upi_id):
                errors.append('Invalid UPI ID')

            taxes = bank_details.get('taxes')
            if not isinstance(taxes, dict):
                errors.append('Taxes must be an object with SGST, CGST, and optional Service Charge fields')
            else:
                # Parse values from taxes
                sgst = normalize_percentage(taxes.get('SGST'))
                cgst = normalize_percentage(taxes.get('CGST'))
                is_tax_included = taxes.get('is_tax_included')
                service_tax_apply = taxes.get('service_tax_apply', False)  # Default to False
                service_charge = normalize_percentage( taxes.get('service_charge')) if service_tax_apply else None

                sgst_value = parse_percentage(sgst)
                cgst_value = parse_percentage(cgst)

                # if sgst_value is None or not validate_taxes(sgst_value):
                #     errors.append("Invalid SGST value")
                # if cgst_value is None or not validate_taxes(cgst_value):
                #     errors.append("Invalid CGST value")

                # # Validate Service Charge if applicable
                # if service_tax_apply:
                #     if service_charge is None:
                #         errors.append("Service Charge is required when service_tax_apply is true")
                #     elif parse_percentage(service_charge) is None or not validate_taxes(parse_percentage(service_charge)):
                #         errors.append("Invalid Service Charge value")

                # Check for errors before proceeding
                if errors:
                    return JsonResponse({'error': 'Validation errors occurred', 'details': errors}, status=400)

                # Construct tax data with percentages as strings
                tax_data = {
                    'SGST': f"{sgst_value}" if sgst_value is not None else None,
                    'CGST': f"{cgst_value}" if cgst_value is not None else None,
                    'is_tax_included': is_tax_included,
                    'service_tax_apply': service_tax_apply,
                    'service_charge': f"{parse_percentage(service_charge)}" if service_tax_apply and service_charge else None
                }

                # Construct bank details
                bank_details = {
                    'bank_name': bank_name,
                    'upi_id': upi_id,
                    'taxes': tax_data
                }

                # Add to update fields
                update_fields['bank_details'] = bank_details

        # Validate working hours
        if 'working_hours' in data:
            working_hours = data['working_hours']
            if not isinstance(working_hours, dict):
                errors.append('Invalid working hours format')
            else:
                for day, details in working_hours.items():
                    if not isinstance(details, dict) or 'isClosed' not in details or 'time_slot' not in details:
                        errors.append(f"Invalid format for working hours on {day}")
                        continue

                    time_slots = details['time_slot']
                    for slot in time_slots:
                        if not validate_time_format(slot.get('start')) or not validate_time_format(slot.get('end')):
                            errors.append(f"Invalid time slot for {day}: {slot}")
                            continue

                update_fields['working_hours'] = working_hours

        if 'special_dates' in data:
            special_dates = data['special_dates']
            if not isinstance(special_dates, list):
                errors.append('Invalid special dates format')
            else:
                for date in special_dates:
                    if not isinstance(date, dict) or 'event_date' not in date or 'event_name' not in date or 'isClosed' not in date or 'time_slot' not in date:
                        errors.append(f"Invalid format for special date: {date}")
                        continue

                    if not validate_date_format(date['event_date']):
                        errors.append(f"Invalid event date format: {date['event_date']}")
                        continue

                    time_slots = date['time_slot']
                    for slot in time_slots:
                        if not validate_time_format(slot.get('start')) or not validate_time_format(slot.get('end')):
                            errors.append(f"Invalid time slot for event {date['event_name']}: {slot}")
                            continue

                update_fields['special_dates'] = special_dates

        # Return validation errors
        if errors:
            return JsonResponse({'error': 'Validation errors occurred', 'details': errors}, status=400)

        # Final Database Update
        if update_fields:
            update_fields['updated_at'] = datetime.utcnow().isoformat()
            result = restrodata_collection.update_one({'_id': restro_id}, {'$set': update_fields})
            if result.modified_count > 0:

                # Calculate and store profile progress
                progress = calculate_profile_progress(restro_id)
                restrodata_collection.update_one({'_id': restro_id}, {'$set': {'profile_progress': str(progress)}})

                # Fetch updated data
                updated_restaurant = restrodata_collection.find_one({"_id": restro_id})
                updated_restaurant["_id"] = str(updated_restaurant["_id"])

                updated_keys = list(update_fields.keys())

                store_notification(
                    collection=db["Notification"],
                    restro_id=restro_id,
                    notification_type="Profile",
                    event="Profile Updated",
                    description="Your restaurant profile has been successfully updated.",
                    details={"restro_id": restro_id,"profile_progress":progress}
                )

                return JsonResponse({
                    'message': 'Restaurant details updated successfully.',
                    'profile_progress': str(progress)
                }, status=200)

        return JsonResponse({'error': 'No changes were made.'}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


#------------------------------edit_dish_image--------------------
@api_view(['PUT'])
def edit_dish_image(request):
    try:
        restro_id = request.data.get('restro_id')
        dish_id = request.data.get('dish_id')
        uploaded_file = request.FILES.get('file')

        # Validating inputs
        if not restro_id:
            return Response({"error": "Restaurant ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not dish_id:
            return Response({"error": "Dish ID is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded_file:
            return Response({"error": "Dish image file is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Connect to the RestaurantMenuData collection
        restaurantmenudata_collection = db["RestaurantMenuData"]

        # Fetch the restaurant
        restaurant = restaurantmenudata_collection.find_one({"_id": restro_id})
        if not restaurant:
            return Response(
                {"error": f"Restaurant with ID '{restro_id}' not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Locate the dish within the restaurant's menu
        menu = restaurant.get('menu', [])
        dish = next((d for d in menu if d['_id'] == dish_id), None)
        if not dish:
            return Response(
                {"error": f"Dish with ID '{dish_id}' not found in restaurant '{restro_id}'."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Upload new image to S3
        unique_file_name = f"{uuid.uuid4()}_{uploaded_file.name}"
        s3_path = f"restaurants/{restro_id}/dishes/{unique_file_name}"
        s3_client.upload_fileobj(uploaded_file, bucket_name, s3_path)

        # Generate new image URL
        new_image_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_path}"

        # Store only the latest image in MongoDB
        dish['dish_img_url'] = new_image_url  

        # Update MongoDB with only the latest image
        result = restaurantmenudata_collection.update_one(
            {"_id": restro_id, "menu._id": dish_id},
            {"$set": {"menu.$.dish_img_url": new_image_url}}
        )

        if result.modified_count == 0:
            return Response({"error": "Failed to update dish image in database."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"message": "Dish image updated successfully.", "new_image_url": new_image_url},
                        status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": "An unexpected error occurred.", "details": str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)
