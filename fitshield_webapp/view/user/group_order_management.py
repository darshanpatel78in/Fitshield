from asyncio.log import logger
from datetime import datetime
import io
import json
import random
import uuid
from bson import ObjectId
import pymongo
import qrcode
from fitshield_webapp.utils.generate_id import generate_group_order_id, generate_host_user_id
from config.connection import db
from fitshield_webapp.utils.qrcode_manager import generate_group_qr_code
from ...utils.logging_utils import get_logger
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def remove_user_from_group(request):
    try:
        if request.method != "DELETE":
            return JsonResponse({"error": "Invalid HTTP method, only DELETE is allowed"}, status=405)

        # Parse request body
        data = json.loads(request.body)
        group_id = data.get("group_id")
        user_id = data.get("user_id")

        # Validate required fields
        if not group_id or not user_id:
            return JsonResponse({"error": "Invalid input: group_id and user_id are required"}, status=400)

        # Access the Cart collection
        cart_collection = db["Cart"]

        # Fetch the group from the cart collection and check if the user exists
        group = cart_collection.find_one({"group_id": group_id})

        if not group:
            return JsonResponse({"error": "Group not found"}, status=404)

        # Check if the user exists in the group_members array
        user_to_remove = next((member for member in group.get("group_members", []) if member["user_id"] == user_id), None)
        if not user_to_remove:
            return JsonResponse({"error": "User not found in group"}, status=404)

        # Check if the user is the host (they cannot be removed)
        if user_to_remove["role"] == "host":
            return JsonResponse({"error": "Host cannot be removed from the group"}, status=400)

        # Remove user from the group_members array
        cart_collection.update_one(
            {"group_id": group_id},
            {"$pull": {"group_members": {"user_id": user_id}}}
        )
        
        # Recalculate cart totals after user removal
        updated_group = cart_collection.find_one({"group_id": group_id})
        group_members = updated_group.get("group_members", [])
        # print("--------------------------------------------------------------------------")
        # print(group_members)
        # Initialize the grand totals
        grand_total_discount = 0
        grand_total_quantity = 0
        grand_total_price = 0

        # Loop through remaining group members to calculate new totals
        for user in group_members:
            grand_total_quantity += user.get("user_quantity", 0)
            grand_total_price += user.get("user_price", 0)
            # Calculate total discount for each user
            for dish in user.get("ordered_dishes", []):
                # grand_total_discount += dish.get("discount", {}).get("full_discount", {}).get("discount_price", 0)
                grand_total_discount += (dish.get("original_price", 0) - dish.get("discount", {}).get("full_discount", {}).get("discount_price", 0))

        # Update the cart totals after removal
        cart_collection.update_one(
            {"group_id": group_id},
            {"$set": {
                "grand_total_quantity": grand_total_quantity,
                "grand_total_price": grand_total_price,
                "grand_total_discount": grand_total_discount
            }}
        )

        # Return success response
        return JsonResponse({"message": "User removed from group"}, status=200)

    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

def get_user_name(user_id):
    """
    Fetches user name from the UserData collection.
    """
    user_data_collection = db["UserData"]
    user = user_data_collection.find_one({"_id": user_id}, {"name": 1, "_id": 0})
    return user["name"] if user else "Unknown"

@csrf_exempt
def create_group(request):
    if request.method == 'POST':
        try:
            # print("lets create group")
            data = json.loads(request.body)
            user_id = data.get("user_id", "").strip()
            is_group = data.get("is_group", False)  # Use the boolean value directly
            restro_id = data.get("restro_id", "").strip()
            floor_name = data.get("floor_name")
            table_number = data.get("table_number", "").strip()
            role = data.get("role", "").strip() if is_group else None  # Role required for group orders

            if not user_id or not restro_id:
                return JsonResponse({"error": "user_id and restro_id are required."}, status=400)
            if is_group and not role:
                return JsonResponse({"error": "role is required for group orders."}, status=400)

            group_data_collection = db["GroupData"]
            user_cart_collection = db["Cart"]

            if is_group:
                group_id = f"group_order_{uuid.uuid4()}"
                # print("genarting group QR code...")
                qr_url = generate_group_qr_code(restro_id, group_id, table_number, floor_name)  # Generate QR code URL
                # print(f"qrrrrrrrrrrrrrrrrrrrrr:{qr_url}")
                
                group_data = {
                    "_id": group_id,
                    "restro_id": restro_id,
                    "qr_code_url": qr_url,
                    "is_lock": False,  
                    "group_members": [
                        {
                            "user_id": user_id,
                            "role": role,
                            "name": get_user_name(user_id),
                            "user_quantity": 0,  # Default
                            "user_price": 0,  # Default
                            "ordered_dishes": [],  # Empty list
                            "user_note": ""  # Default empty note
                        }
                    ],
                    "created_at": datetime.utcnow().isoformat()
                }
                group_data_collection.insert_one(group_data)

                cart_id = f"group_cart_{uuid.uuid4()}"
                user_cart = {
                    "_id": cart_id,
                    "restro_id": restro_id,
                    "user_id": None,  
                    "group_id": group_id,
                    "is_lock": False,  
                    "is_order_completed": False,  
                    "group_members": [
                        {
                            "user_id": user_id,
                            "role": role,
                            "name": get_user_name(user_id),
                            "user_quantity": 0,  # Default
                            "user_price": 0,  # Default
                            "ordered_dishes": [],  # Empty list
                            "user_note": ""  # Default empty note
                        }
                    ],
                    "created_at": datetime.utcnow().isoformat()
                }
                user_cart_collection.insert_one(user_cart)

                return JsonResponse({
                    "message": "Group created successfully.",
                    "group_id": group_id,
                    "cart_id": cart_id,
                    "qr_code_url": qr_url
                }, status=201)

            else:
                # Create a new cart for the individual user
                cart_id = f"user_cart_{uuid.uuid4()}"
                user_cart = {
                    "_id": cart_id,
                    "user_id": user_id,
                    "restro_id": restro_id,
                    "group_id": None,  # No group ID for individual orders
                    "is_order_completed": False,  
                    "created_at": datetime.utcnow().isoformat()
                }
                user_cart_collection.insert_one(user_cart)

                return JsonResponse({  
                    "message": "Individual order cart created successfully.",
                    "cart_id": cart_id
                }, status=201)

        except Exception as e:
            return JsonResponse({"error": "An unexpected error occurred.", "details": str(e)}, status=500)

    else:
        return JsonResponse({"error": "Invalid HTTP method. Use POST."}, status=405)



#-------------------------group_join-----------------------

@csrf_exempt
def group_join(request):
    if request.method == 'POST':
        logger.warning("Invalid HTTP method used for group_join. Only POST is allowed.")
        try:
            data = json.loads(request.body)
            logger.debug("Request body: %s", data)

            group_id = data.get("group_id")
            user_id = data.get("user_id")

            # group_order_collection = db["GroupData"]
            group_cart_collection = db["Cart"]
            userdata_collection = db["UserData"]

            # group_order = group_order_collection.find_one({"_id": group_id}, {"group_members": 1})
            group_cart = group_cart_collection.find_one({"group_id": group_id}, {"_id": 1, "group_members": 1})
            user = userdata_collection.find_one({"_id": user_id}, {"name": 1, "_id": 0})

            # if not group_order:
            #     return JsonResponse({"error": "Group order not found"}, status=404)

            if not group_cart:
                logger.error(f"No cart found for group_id: {group_id}")
                return JsonResponse({"error": "Cart not found for the provided group_id"}, status=404)
            
            user_name = user["name"] if user and "name" in user else "Unknown"
            cart_id = group_cart["_id"]
            logger.info("Checking if group order exists with ID: %s", group_id)

            # # Check if the user is already in grouporder
            # existing_member = next((member for member in group_order["group_members"] if member["user_id"] == user_id), None)
            # if existing_member:
            #     member_count = len(group_order["group_members"])
            #     return JsonResponse({
            #         "message": "User has already been added to this Group Order",
            #         "group_id": group_id,
            #         "user_id": user_id,
            #         "cart_id": cart_id,
            #         "member_count": member_count
            #     }, status=200)

            # # Add User to grouporder
            # group_order_collection.update_one(
            #     {"_id": group_id},
            #     {"$push": {"group_members": {"user_id": user_id, "role": "member"}}}
            # )

            # Check if the user exists in group_cart
            existing_cart_member = next((member for member in group_cart.get("group_members", []) if member["user_id"] == user_id), None)
            if not existing_cart_member:
                new_user_entry = {
                    "user_id": user_id,
                    "role": "member",
                    "name": user_name,
                    "user_quantity": 0,
                    "user_price": 0,
                    "ordered_dishes": [],
                    "user_note": ""
                }

                existing_member = next((member for member in group_cart["group_members"] if member["user_id"] == user_id), None)
                if existing_member:
                    member_count = len(group_cart["group_members"])
                    return JsonResponse({
                        "message": "User has already been added to this Group Order",
                        "group_id": group_id,
                        "user_id": user_id,
                        "cart_id": cart_id,
                        "member_count": member_count
                    }, status=200)

                
                # Add User to groupcart
                group_cart_collection.update_one(
                    {"_id": cart_id},
                    {"$push": {"group_members": new_user_entry}}
                )

            logger.info("User '%s' successfully added to group order '%s'.", user_id, group_id)

            # No need to re-fetch the group, use in-memory data
            member_count = len(group_cart["group_members"]) + 1  # Since we just added one

            return JsonResponse({
                "message": "You are added to Group Order",
                "group_id": group_id,
                "user_id": user_id,
                "cart_id": cart_id,
                "member_count": member_count
            })

        except Exception as e:
            logger.error("An unexpected error occurred while joining the group: %s", str(e), exc_info=True)
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid HTTP method"}, status=405)


@csrf_exempt
def group_lock(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            group_id = data.get("group_id")
            user_id = data.get("user_id")
            is_locked = data.get("is_locked")  # True or False

            if not group_id or not user_id or is_locked is None:
                return JsonResponse({"error": "group_id, user_id, and is_locked are required."}, status=400)

            # Access GroupData and Cart collections
            group_data_collection = db["GroupData"]
            cart_collection = db["Cart"]

            # Retrieve the group data
            group_data = group_data_collection.find_one({"_id": group_id})

            # if not group_data:
            #     return JsonResponse({"error": "Group data not found."}, status=404)

            # Check if the user is the host
            host_user = next((member for member in group_data.get("group_members", []) if member.get("role") == "host"), None)
            if not host_user or host_user.get("user_id") != user_id:
                return JsonResponse({"error": "Only the host can lock or unlock the group order."}, status=403)

            # Update the is_locked status in GroupData
            # group_data_collection.update_one(
            #     {"_id": group_id},
            #     {"$set": {"is_locked": is_locked}}
            # )

            # Update the is_locked status in Cart for the corresponding group_id
            cart_collection.update_many(
                {"group_id": group_id},
                {"$set": {"is_lock": is_locked}}
            )

            action = "locked" if is_locked else "unlocked"
            return JsonResponse({"message": f"Group order {action} successfully."}, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)
    else:
        return JsonResponse({"error": "Invalid HTTP method. Use POST."}, status=405)









