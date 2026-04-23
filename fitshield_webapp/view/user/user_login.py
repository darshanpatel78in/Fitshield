from datetime import date, datetime
import json
import time
import uuid
from django.views.decorators.csrf import csrf_exempt
import requests
import random
from random import randint
from config.connection import db
from django.http import JsonResponse
from rest_framework.response import Response
from fitshield.settings import WEATHER_API_KEY, WEATHER_API_URL
from fitshield_webapp.AI.AIModel.User.get_personalize_dish import calculate_nutrient_percentages, user_data_process
from fitshield_webapp.utils.format_validate import generate_otp
from fitshield_webapp.utils.generate_id import generate_user_cart, generate_user_id
from rest_framework import status
from fitshield_webapp.utils.otp_helpers import send_otp_via_sms
from fitshield_webapp.utils.serializers import SendOTPSerializer
from fitshield_webapp.view.user.utils import validate_and_extract_data

@csrf_exempt
def user_data(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            user_id = data.get("user_id")
            is_exist = data.get("is_exist")
            is_personalized = data.get("is_personalized")

            if not user_id:
                return JsonResponse({"error": "User ID is required."}, status=400)            

            userdata_collection = db["UserData"]
            user = userdata_collection.find_one({"_id": user_id})           

            if not user:
                return JsonResponse({"error": "User not found."}, status=404)

            print(f"user_data: {user_data}")
            user_data_response = {
                key: user[key] for key in user if key not in ["created_at", "updated_at"]
            }
            user_data_response.update({
            "created_at": user.get("created_at"),
            "updated_at": user.get("updated_at")
            }) if is_exist else user_data_response.clear()
            
            # Validate and prepare data for update
            user_data_update = validate_and_extract_data(data)
            user_data_update["updated_at"] = datetime.utcnow().isoformat()

            userdata_collection.update_one({"_id": user_id}, {"$set": user_data_update})

            if is_personalized:
                # print("Running user model for personalization...")
                # print("user:", user)
                
                user_input = user_data_process(user) 
                macros = calculate_nutrient_percentages(user_input)

                macro_info = {
                "total_kcal": {"value": round(macros["tdee"], 2), "unit": "kcal"},
                "protein": {"value": round(macros["p"], 2), "unit": "g"},
                "carbs": {"value": round(macros["c"], 2), "unit": "g"},
                "fats": {"value": round(macros["fa"], 2), "unit": "g"},
                "fiber": {"value": round(macros["fiber"], 2), "unit": "g"}
                }

                userdata_collection.update_one(
                {"_id": user_id},
                {"$set": {
                    "goals.default_goal.kcal": macro_info["total_kcal"],
                    "goals.default_goal.nutrients.protein": macro_info["protein"],
                    "goals.default_goal.nutrients.carbs": macro_info["carbs"],
                    "goals.default_goal.nutrients.fats": macro_info["fats"],
                    "goals.default_goal.nutrients.fiber": macro_info["fiber"],
                    "updated_at": datetime.utcnow().isoformat()
                }}
                )

                # userdata_collection.update_one(
                #     {"_id": user_id},
                #     {"$set": {
                #         "goals.default_goal.kcal": macro_info["total_kcal"],
                #         "goals.default_goal.nutrients": {
                #             "protein": macro_info["protein"],
                #             "carbs": macro_info["carbs"],
                #             "fats": macro_info["fats"],
                #             "fiber": macro_info["fiber"]
                #         },
                #         "updated_at": datetime.utcnow()
                #     }}
                # )
            user = userdata_collection.find_one({"_id": user_id}) 
            print("=====================================")
            print(user)
                
            return JsonResponse({
                "message": "User data updated successfully!",
                "user_data": user
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({
            "error": "Invalid HTTP method. Only POST is allowed."
        }, status=405)

@csrf_exempt
def get_temperature(request):
    try:
        # Parse JSON data from the request body
        data = json.loads(request.body)
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        # Validate the input
        if not latitude or not longitude:
            return JsonResponse({"error": "Latitude and Longitude are required."}, status=400)

        # Call the weather API
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": WEATHER_API_KEY,
            "units": "metric"  # Metric ensures the temperature is in Celsius
        }
        response = requests.get(WEATHER_API_URL, params=params)
        weather_data = response.json()

        # Check if the response from the weather API is valid
        if response.status_code != 200:
            return JsonResponse({"error": weather_data.get("message", "Unable to fetch temperature.")}, status=response.status_code)

        # Extract temperature from the response
        temperature = weather_data["main"]["temp"]

        # Return latitude, longitude, and temperature in JSON format
        return JsonResponse({
            "latitude": latitude,
            "longitude": longitude,
            "temperature": temperature
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# @csrf_exempt
# def fetch_user_data(request):
#     if request.method == 'GET':
#         try:
#             user_id = request.GET.get("user_id")
#             if not user_id:
#                 return JsonResponse({
#                     "error": "User ID is required."
                    
#                 }, status=400)

#             userdata_collection = db["UserData"]
#             user = userdata_collection.find_one({"_id": user_id})

#             if not user:
#                 return JsonResponse({
#                     "error": "User not found."
#                 }, status=404)

#             return JsonResponse({
#                 "message": "User data fetched successfully!",
#                 "user_data": user
#             }, status=200)

#         except Exception as e:
#             return JsonResponse({
#                 "error": str(e)
#             }, status=500)

#     else:
#         return JsonResponse({
#             "error": "Invalid HTTP method. Only GET is allowed."
#         }, status=405)
    

# #************************pooja*************** 
# @csrf_exempt
# def scan_restaurant(request):
#     if request.method == "POST":
#         try:
#             data = json.loads(request.body)
#             restro_id = data.get('restro_id')
#             table_number = data.get('table_number')
#             floor_name = data.get('floor_name')

#             # Validate input
#             if not restro_id or not table_number or not floor_name:
#                 return JsonResponse({"status": "error", "message": "Invalid QR code or table not found."}, status=400)

#             # Access the RestroData collection
#             restaurant_collection = db["RestroData"]

#             # Fetch restaurant details by restro_id
#             restaurant = restaurant_collection.find_one({"_id": restro_id})
#             if not restaurant:
#                 return JsonResponse({"status": "error", "message": "Invalid QR code or table not found."}, status=404)

#             # Search for the floor in the floor_detail array
#             floors = restaurant.get("floor_detail", [])
#             floor = next((f for f in floors if f.get("floor_name") == floor_name), None)
#             if not floor:
#                 return JsonResponse({"status": "error", "message": "Invalid QR code or table not found."}, status=404)

#             # Search for the table in the tables array within the floor
#             tables = floor.get("tables", [])
#             table = next((t for t in tables if t.get("table_number") == table_number), None)
#             if not table:
#                 return JsonResponse({"status": "error", "message": "Invalid QR code or table not found."}, status=404)

#             # Prepare success response
#             return JsonResponse({
#                 "status": "success",
#                 "restaurant_details": {
#                     "name": restaurant.get("name"),
#                     "address": restaurant.get("address")
#                 },
#                 "table_details": {
#                     "table_number": table.get("table_number"),
#                     "status": "available",  # Assuming availability
#                     "floor_name": floor.get("floor_name")
#                 }
#             })

#         except json.JSONDecodeError:
#             return JsonResponse({"status": "error", "message": "Invalid JSON format."}, status=400)
#         except Exception as e:
#             return JsonResponse({"status": "error", "message": str(e)}, status=500)
#     else:
#         return JsonResponse({"status": "error", "message": "Invalid HTTP method. Use POST."}, status=405)

@csrf_exempt
def user_exists(request):
    try:
        # Parse the JSON data from the request body
        data = json.loads(request.body.decode("utf-8"))

        # Extract country_code and phone_number from the request body
        country_code = data.get("country_code", "").strip()
        phone_number = data.get("phone_number", "").strip()

        # Validate input
        if not country_code or not phone_number:
            return JsonResponse(
                {"error": "Both country_code and phone_number must be provided."},
                status=400
            )

        # Access the UserData collection
        userdata_collection = db["UserData"]

        # Check if the user exists in the database
        document = userdata_collection.find_one({
            "country_code": country_code,
            "mobile_number": phone_number
        })

        if document:
            return JsonResponse(
                {
                    "is_exist": True,
                    "user_id": str(document.get("_id")),  # Convert ObjectId to string
                    "message": "User already exists in the database."
                },
                status=200
            )
        else:
            return JsonResponse(
                {
                    "is_exist": False,
                    "user_id": "",
                    "message": "User does not exist in the database."
                },
                status=200
            )
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON format."},
            status=400
        )
    except Exception as e:
        return JsonResponse(
            {"error": "An unexpected error occurred.", "details": str(e)},
            status=500
        )



@csrf_exempt
def add_user(request):
    if request.method == "POST":
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body.decode("utf-8"))

            # Extract required fields
            name = data.get("name", "").strip()
            phone_number = data.get("phone_number", "").strip()
            country_code = data.get("country_code", "").strip()
            latitude = data.get("latitude",None)
            longitude = data.get("longitude",None)

            # Validate input
            if not name or not phone_number or not country_code:
                return JsonResponse(
                    {"message": "Name, phone_number, country_code are required."},
                    status=400
                )

            # Access the UserData collection
            userdata_collection = db["UserData"]

            # Check if the user already exists
            existing_user = userdata_collection.find_one({
                "country_code": country_code,
                "mobile_number": phone_number
            })

            if existing_user:
                return JsonResponse(
                    {"message": "User already exists.", "user_id": existing_user.get("_id")},
                    status=200
                )

            # Generate a customized user_id in the format (user_<name>_<randomnumber>)
            random_number = uuid.uuid4()  # Generate a 4-digit random number
            user_id = f"user_{name}_{random_number}"

            # Create a new user entry with the generated user_id as the _id field
            new_user = {
                "_id": user_id,  # Store the user_id in the _id field
                "name": name,
                "mobile_number": phone_number,
                "country_code": country_code,
                "latitude": latitude,
                "longitude": longitude,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            userdata_collection.insert_one(new_user)

            # Return success response
            return JsonResponse(
                {
                    "message": "User added successfully.",
                    "user_id": user_id
                },
                status=201
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON format."},
                status=400
            )
        except Exception as e:
            return JsonResponse(
                {"message": "An unexpected error occurred.", "details": str(e)},
                status=500
            )
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use POST."}, status=405)
    
@csrf_exempt
def get_user_data(request):
    if request.method == "GET":
        try:
            # Get the user_id from query parameters
            user_id = request.GET.get("user_id", "").strip()

            # Validate input
            if not user_id:
                return JsonResponse({"message": "user_id is required."}, status=400)

            # Access the UserData collection
            userdata_collection = db["UserData"]

            # Fetch the user data by user_id
            user_data = userdata_collection.find_one({"_id": user_id}, {"_id": 0})  # Exclude MongoDB's _id field

            if not user_data:
                return JsonResponse({"message": "User not found."}, status=404)

            # Return user data
            return JsonResponse(user_data, safe=False)

        except Exception as e:
            return JsonResponse({"message": "An unexpected error occurred.", "details": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)


otp_store = {}

@csrf_exempt
def user_send_otp(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        country_code = data.get('country_code')
        phone_number = data.get('phone_number')

        if not country_code or not phone_number:
            return JsonResponse({'error': 'Both country_code and phone_number are required.'}, status=400)

        # Concatenate country_code and phone_number to form the full phone number
        phone = f"{country_code.strip('+')}{phone_number.strip()}"
        
        # Validate the phone number format
        try:
            phone_int = int(phone)  # Ensure the concatenated phone is numeric
        except ValueError:
            return JsonResponse({'error': 'Invalid phone number format.'}, status=400)
        
        otp = generate_otp()

        otp_store[phone] = {'otp': otp, 'expires_at': time.time() + 120}

        hisocial_api_url = 'https://hisocial.in/api/send'
        instance_id = "679DF139A477D"  
        access_token = "679ded35dde2c"

        try:
            phone_int = int(''.join(filter(str.isdigit, str(phone))))
        except ValueError:
            return JsonResponse({'error': 'Invalid phone number format.'}, status=400)

        payload = {
            "number": phone_int,
            "type": "whatsapp",
            "message": f"""Hi, your Fitshield code is {otp}.Use it in 2 minutes or it vanishes like a ninja!""",
            "instance_id": instance_id,
            "access_token": access_token
        }

        # retry logic try upto 3 times
        attepts = 0
        success = False
        while attepts < 3 and not success:
            attepts += 1
            response = requests.post(hisocial_api_url, json=payload)
            if response.status_code == 200:
                success = True
            else:
                # print("retrying...")
                time.sleep(2) #wait for 2 second before retrying

        # Parse response or error message from hisocial API
        if success:
            return JsonResponse(
                {
                    "message": "OTP sent successfully.",
                    "otp": str(otp)  # Return the OTP (omit in production for security reasons)
                },
                status=200
            )
        else:
            try:
                message = response.json()
            except ValueError:
                message = {"details": "Failed to parse error response from hisocial API."}

            return JsonResponse(
                {
                    "error": "Failed to send OTP.",
                    "details": message
                },
                status=500
            )
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid JSON format."},
            status=400
        )
    except Exception as e:
        return JsonResponse(
            {"error": "An unexpected error occurred.", "details": str(e)},
            status=500
        )
    




    