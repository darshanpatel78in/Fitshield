from datetime import datetime
import json
import logging
import pytz
from fitshield_webapp.utils.generate_id import generate_entry_id, generate_multiple_query_id, generate_query_id
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse

from fitshield_webapp.utils.mail import send_admin_email
from ...utils.logging_utils import get_logger

logger = logging.getLogger(__name__)

@csrf_exempt
def submit_query(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            restro_id = data.get('restro_id')
            # logger = get_logger(restro_id)
            #logger.debug(f"Request data: {data}")
             
            restaurant_name = data.get("restaurant_name")
            email = data.get("email")
            contact_number = data.get("contact_number")
            query = data.get('query')
            query_description = data.get('query_description')
            status = data.get('status','Pending')

            if not restro_id or not restaurant_name or not query or not query_description:
               # logger.warning("Validation failed: Missing required fields.")
                return JsonResponse({'error': 'Missing required fields'}, status=400)

            if not email and not contact_number:
                return JsonResponse({'error': 'Either Email or Contact Number required'}, status=400)

            query_collection = db["RestaurantQuery"]
            existing_entry = query_collection.find_one({'restro_id': restro_id})

            query_id = generate_multiple_query_id()
            new_query = {
                "query_id": query_id,
                "restaurant_name": restaurant_name,
                "email": email if email else None,
                "contact_number": contact_number if contact_number else None,
                "query": query,
                "query_description": query_description,
                "status": status,
                "created_at": datetime.utcnow().isoformat()
            }

            if existing_entry:
               # logger.info("Updating existing query entry.")
                query_collection.update_one(
                    {'restro_id': restro_id},
                    {
                        '$push': {'queries': new_query},
                        '$set': {'updated_at': datetime.utcnow().isoformat()}
                    }
                )
                query_id = existing_entry["_id"]
            else:
                query_id = generate_query_id(restro_id)
               # logger.info("Creating a new query entry.")
                query_data = {
                    "_id": query_id,
                    "restro_id": restro_id,
                    "queries": [new_query],
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
                query_collection.insert_one(query_data)
            
            # send mail to admin and inform them
            send_admin_email(
                issue_type="General Query",
                restaurant_name=restaurant_name, 
                restro_id=restro_id,  
                query=query, 
                description=query_description, 
                from_email=email 
            )
            #logger.info("Query submitted successfully.")
            return JsonResponse({'message': 'Query submitted successfully', 'query_id': query_id}, status=200)

        except json.JSONDecodeError:
           # logger.error("Invalid JSON format.")
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)

        except Exception as e:
           # logger.exception("Error submitting query.")
            return JsonResponse({'error': f"Error submitting query: {str(e)}"}, status=500)

    # logger.warning("Invalid HTTP method used for submit_query endpoint.")
    return JsonResponse({'error': 'Invalid HTTP method. Only POST is allowed.'}, status=405)


@csrf_exempt
def get_in_touch(request):
    if request.method == 'POST':
        try:
            contact_collection = db["ContactUs"]  # Replace with your collection name
            restrodata_collection = db["RestroData"]

            # Parse the request body
            data = json.loads(request.body)
            restro_id = data.get("restro_id")
            restaurant_name = data.get("restaurant_name")
            email = data.get("email",None)
            contact_number = data.get("contact_number",None)
            message = data.get("message")
            
            # Check restro_id exist
            exist_restaurant = restrodata_collection.find_one({"_id": restro_id})
            if not exist_restaurant:
                return JsonResponse({"error": "Restaurant not exist"})

            # Validate required fields
            if not all([restro_id, restaurant_name, message]):
                return JsonResponse({"error": "Missing required fields."}, status=400)

            # Check if an entry already exists for the restaurant
            existing_entry = contact_collection.find_one({"restro_id": restro_id})


            if existing_entry:
                # Add the new message to the existing entry
                contact_collection.update_one(
                    {"restro_id": restro_id},
                    {
                        "$push": {
                            "messages": {
                                "message": message,
                                "created_at":datetime.utcnow().isoformat()
                            }
                        },
                        "$set": {"updated_at": datetime.utcnow().isoformat()}
                    }
                )
                return JsonResponse({"message": "Message added successfully."}, status=200)

            entry_id = generate_entry_id(restaurant_name)
            # Create a new entry
            new_entry = {
                "_id": entry_id,
                "restro_id": restro_id,
                "restaurant_name": restaurant_name,
                "email": email,
                "contact_number": contact_number,
                "messages": [
                    {
                        "message": message,
                        "created_at": datetime.utcnow().isoformat()
                    }
                ],
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            contact_collection.insert_one(new_entry)
            return JsonResponse({"message": "Message submitted successfully."}, status=201)

        except Exception as e:
            return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid HTTP method."}, status=405)
