from datetime import datetime
import json
from logging.handlers import RotatingFileHandler
import uuid
import pytz
from ...utils.logging_utils import get_logger
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response
from django.utils.timezone import now, timedelta


# Notification Management

#----------------------------------POOJANotifications------------------------------

# Define IST timezone
ist_timezone = pytz.timezone("Asia/Kolkata")

# @csrf_exempt
# def add_notification(request):
#     if request.method == "POST":
#         try:
#             # Access the collection
#             notifications_collection = db['Notification']  # Replace with your collection name

#             # Parse incoming request data
#             request_data = json.loads(request.body)

#             # Extract `restro_id` and `notification`
#             restro_id = request_data.get("restro_id")  # Restaurant ID
#             notification = request_data.get("notification")  # Notification details

#             # Validate required fields
#             if not (restro_id and notification):
#                 return JsonResponse({"message": "restro_id and notification are required!"}, status=400)

#             # Generate a unique `_id` for the notification
#             notification["_id"] = f"{restro_id}_{notification['type']}_{str(uuid.uuid4())[:8]}"  

#             # Add timestamps to the notification
#             notification["created_at"] = datetime.utcnow().isoformat() 
#             notification["updated_at"] =datetime.utcnow().isoformat() 
#             # notification["isRead"] = False  # Default is read status as False

#             # Check if the restaurant document already exists in the collection
#             existing_document = notifications_collection.find_one({"_id": restro_id})

#             if existing_document:
#                 # Append the new notification to the existing `notifications` array
#                 notifications_collection.update_one(
#                     {"_id": restro_id},
#                     {"$push": {"notifications": notification}}
#                 )
#             else:
#                 # Create a new document for the restaurant with the first notification
#                 notifications_collection.insert_one({
#                     "_id": restro_id,
#                     "notifications": [notification]
#                 })

#             # Return a success response
#             return JsonResponse({"message": "Notification added successfully!", "notification": notification}, status=201)

#         except Exception as e:
#             # print(f"Error adding notification: {e}")  # Improved error logging
#             return JsonResponse({"message": "Internal server error!"}, status=500)

#     return JsonResponse({"message": "Invalid request method!"}, status=405)

@csrf_exempt
def get_notifications(request):
    if request.method == "GET":
        try:
            restro_id = request.GET.get("restro_id")

            if not restro_id:
                return JsonResponse({"error": "restro_id is required"}, status=400)

            now = datetime.utcnow()  # Keep as datetime object
            one_week_ago = now - timedelta(weeks=1)  # Keep as datetime object

            restaurant = db["Notification"].find_one({"_id": restro_id}, {"notifications": 1})

            if not restaurant or "notifications" not in restaurant:
                return JsonResponse({"notifications": []}, status=200)

            valid_notifications = []

            for notification in restaurant["notifications"]:
                notification_type = notification.get("type")
                event_type = notification.get("event")
                created_at = notification.get("created_at")
                expires_at = notification.get("expires_at") 

                # Convert created_at to datetime before comparison
                try:
                    created_at_dt = datetime.fromisoformat(created_at)
                except:
                    print(f"Skipping invalid created_at: {created_at}")
                    continue  

                if notification_type == "Profile":
                    valid_notifications.append(notification)
                    continue  

                if notification_type == "Dish" and event_type in ["Dish Added", "Dish Updated"]:
                    if created_at_dt >= one_week_ago: 
                        valid_notifications.append(notification)
                        continue
 
                if notification_type == "Order" and expires_at:
                    try:
                        expires_at_dt = datetime.fromisoformat(expires_at)
                        if expires_at_dt >= now: 
                            valid_notifications.append(notification)
                    except:
                        print(f"Skipping invalid expires_at: {expires_at}")
                        continue

            return JsonResponse({"notifications": valid_notifications}, status=200)

        except Exception as e:
            return JsonResponse({"error": f"Error fetching notifications: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid HTTP method, only GET is allowed"}, status=405)
