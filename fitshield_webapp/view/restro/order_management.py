from datetime import date, datetime, timezone
import json
from time import localtime

from pymongo import DESCENDING
import pytz

from fitshield_webapp.view.restro.save_json import save_json_to_file
from ...utils.logging_utils import get_logger
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import JsonResponse
from django.utils.timezone import localtime
 
# Define IST timezone
ist_timezone = pytz.timezone("Asia/Kolkata")

@csrf_exempt
def order_history(request):
    if request.method == "GET":
        try:
            restro_id = request.GET.get('restro_id')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')

            if not restro_id:
                return JsonResponse({"message": "restro_id query parameter is required"}, status=400)

            user_data_collection = db["UserData"]
            user_order_collection = db["UserOrder"]
            restaurant_review_collection = db["RestaurantReview"]
            cart_collection = db["Cart"]  
            group_data_collection = db["GroupData"] 

            total_received_orders = list(user_order_collection.find({
                "restro_id": restro_id,
                "status": "Completed"
            }))

            # if not total_received_orders:
            #     return JsonResponse({"message": "No orders found for this restaurant"}, status=404)

            total_earnings = sum(order.get("amount", {}).get("payable_amount", 0.0) for order in total_received_orders)


            # Calculate today's earnings using ISO string comparisons
            today = date.today()
            start_datetime_today = datetime.combine(today, datetime.min.time()) 
            end_datetime_today = start_datetime_today.replace(hour=23, minute=59, second=59)
            start_today_iso = start_datetime_today.isoformat()
            end_today_iso = end_datetime_today.isoformat()

            # Filter orders for today only
            today_orders = list(user_order_collection.find({
                "restro_id": restro_id,
                "status":"Completed",
                "created_on": {"$gte": start_today_iso, "$lte": end_today_iso}
            }))

            today_earnings = sum(order.get("amount", {}).get("payable_amount", 0.0) for order in today_orders)

            # Prepare filtered query
            
            filtered_query = {"restro_id": restro_id, "status": "Completed"}
            if start_date and end_date:
                try:
                    # Convert query parameters (dd/mm/yyyy) to datetime objects
                    start_datetime = datetime.strptime(start_date, "%d/%m/%Y")
                    end_datetime = datetime.strptime(end_date, "%d/%m/%Y")
                    end_datetime = end_datetime.replace(hour=23, minute=59, second=59)
                    
                    # Convert to ISO format for comparison with stored strings
                    filtered_query["created_on"] = {
                        "$gte": start_datetime.isoformat(),
                        "$lte": end_datetime.isoformat()
                    }
                except ValueError:
                    return JsonResponse({"message": "Invalid date format. Use dd/mm/yyyy."}, status=400)

            # Filter orders based on query parameters
            filtered_orders_date = list(user_order_collection.find(filtered_query))
            filtered_earnings = sum(order.get("amount", {}).get("payable_amount", 0.0) for order in filtered_orders_date)

            result = []

            # Helper function to parse the ISO date string to a datetime object
            def parse_created_on(created_on):
                if isinstance(created_on, str):
                    return datetime.fromisoformat(created_on)
                return created_on

            for order in filtered_orders_date:
                order_data = {}
                created_on = order.get("created_on")
                created_on_dt = parse_created_on(created_on) if created_on else None

                # Check if the order is a group order or an individual order
                if order.get("group_id"):  # Group order
                    group_id = order.get("group_id")
                    group_data = group_data_collection.find_one({"_id": group_id})

                    # Find the host's user_id from the group data
                    host_user_id = None
                    for member in group_data.get("group_members", []):
                        if member.get("role") == "host":
                            host_user_id = member.get("user_id")
                            break

                    # Fetch host details
                    if host_user_id:
                        host_user = user_data_collection.find_one({"_id": host_user_id})
                        host_username = host_user.get("name") if host_user else "Unknown Host"
                        host_phone_number = host_user.get("mobile_number") if host_user else "Unknown Number"
                    else:
                        host_username = "Unknown Host"
                        host_phone_number = "Unknown Number"

                    # Fetch the group cart for dish details
                    group_cart = cart_collection.find_one({"_id": order.get("cart_id")})
                    group_dishes = []
                    if group_cart:
                        for user_dish in group_cart.get("group_members", []):
                            for dish in user_dish.get("ordered_dishes", []):
                                group_dishes.append({
                                    "cart_id":order.get("cart_id"),
                                    "dish_id": dish.get("dish_id"),
                                    "name": dish.get("name"),
                                    "quantity": dish.get("quantity"),
                                    "price": dish.get("price"),
                                    "total": dish.get("total")
                                })

                    order_data = {
                        "bill_no": order.get("bill_no"),
                        "username": host_username, 
                        "phone_number": host_phone_number,  
                        "date": created_on_dt.strftime("%d/%m/%Y") if created_on_dt else "Unknown Date",
                        "time": created_on_dt,
                        "table_number": f"{order.get('table_number')}",
                        "order_no": int(f"{order.get('order_no')}"),
                        "payment_method": order.get("payment_method"),
                        "payment_status": order.get("payment_status"),
                        "amount": {
                            "subtotal": order.get("amount", {}).get("subtotal", 0.0),
                            "Service Tax": order.get("amount", {}).get("service_tax", 0.0),
                            "GST": order.get("amount", {}).get("gst", 0.0),
                            "discount_amount": order.get("amount", {}).get("discount_amount", 0.0),
                            "discount_percentage": order.get("amount", {}).get("discount_percentage", 0.0),
                            "payable_amount": order.get("amount", {}).get("payable_amount", 0.0)
                        },
                        "dishes": group_dishes,
                        "rating_value": None 
                    }

                else:  # Individual order
                    user_id = order.get("user_id")
                    user = user_data_collection.find_one({"_id": user_id})
                    if not user:
                        continue
                    review = restaurant_review_collection.find_one(
                        {"restro_id": restro_id, "reviews.order_id": order["_id"]},
                        {"reviews.$": 1}
                    )
                    review_data = review["reviews"][0] if review else {}

                    # Fetch the individual cart for dish details
                    cart = cart_collection.find_one({"_id": order.get("cart_id")}) 
                    individual_dishes = [
                        {
                            "dish_id": dish.get("dish_id"),
                            "name": dish.get("name"),
                            "quantity": dish.get("quantity"),
                            "price": dish.get("price"),
                            "total": dish.get("total")
                        }
                        for dish in cart.get("ordered_dishes", [])
                    ] if cart else []

                    order_data = {
                        "bill_no": order.get("bill_no"),
                        "username": user.get("name"),
                        "phone_number": user.get("mobile_number"),
                        "date": created_on_dt.strftime("%d/%m/%Y") if created_on_dt else "Unknown Date",
                        "time": created_on_dt,
                        "table_number": f"{order.get('table_number')}",
                        "order_no": int(f"{order.get('order_no')}"),
                        "payment_method": order.get("payment_method"),
                        "payment_status": order.get("payment_status"),
                        "amount": {
                            "subtotal": order.get("amount", {}).get("subtotal", 0.0),
                            "Service Tax": order.get("amount", {}).get("service_tax", 0.0),
                            "GST": order.get("amount", {}).get("gst", 0.0),
                            "discount_amount": order.get("amount", {}).get("discount_amount", 0.0),
                            "discount_percentage": order.get("amount", {}).get("discount_percentage", 0.0),
                            "payable_amount": order.get("amount", {}).get("payable_amount", 0.0)
                        },
                        "dishes": individual_dishes,
                        "rating_value": {
                            "All": review_data.get("rating_value", None),
                            "Ambiance": review_data.get("ambiance", None),
                            "Food Quality": review_data.get("food_quality", None),
                            "Service": review_data.get("service", None),
                            "Menu": review_data.get("menu", None),
                            "feedback": review_data.get("feedback", None)
                        } if review_data else None
                    }

                result.append(order_data)

            response = {
                "total_earnings": total_earnings,
                "filtered_earnings": filtered_earnings,
                "today_earnings": today_earnings, 
                "orders": result
            }
            return JsonResponse(response, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({'message': 'Invalid request method! Only GET is allowed.'}, status=405)


@csrf_exempt
def table_order_details(request):
    if request.method == "GET":
        try:
            order_id = request.GET.get('order_id')

            if not order_id:
                return JsonResponse({"message": "order_id query parameter is required"}, status=400)

            user_data_collection = db["UserData"]
            user_order_collection = db["UserOrder"]
            cart_collection = db["Cart"]

            # Fetch the order
            order = user_order_collection.find_one({"_id": order_id})
            if not order:
                return JsonResponse({"message": "No order found with the provided order ID"}, status=404)

            # Fetch the cart associated with the order
            cart = cart_collection.find_one({"_id": order.get("cart_id")})
            if not cart:
                return JsonResponse({"message": "No cart found for the order"}, status=404)

            created_on = order.get("created_on")
            created_on_dt = datetime.fromisoformat(created_on) if isinstance(created_on, str) else created_on

            dishes = []
            username = "Unknown User"
            phone_number = "Unknown Number"

            # Handling group orders: fetch all members' dishes and host details
            if cart.get("group_id"):  # Group order
                for member in cart.get("group_members", []):
                    user_id = member.get("user_id")
                    member_user = user_data_collection.find_one({"_id": user_id})
                    member_name = member.get("name")
                    member_phone = member_user.get("mobile_number") if member_user else "Unknown Number"

                    # Aggregate dishes for each member
                    for dish in member.get("ordered_dishes", []):
                        dishes.append({
                            "dish_id": dish.get("dish_id"),
                            "name": dish.get("name"),
                            "variant": dish.get("variant"),
                            "size": dish.get("size"),
                            "quantity": dish.get("quantity"),
                            "price": dish.get("price"),
                            "total": dish.get("total"),
                            "dish_img_url": dish.get("dish_img_url"),
                            "discount": dish.get("discount")
                        })

                    # Assign host details as username and phone number
                    if member.get("role") == "host":
                        username = member_name if member_name else "Unknown Host"
                        phone_number = member_phone if member_phone else "Unknown Number"
                        
            else:  # Individual order
                # Fetch individual user details for individual orders
                user_id = cart.get("user_id")
                if user_id:
                    user = user_data_collection.find_one({"_id": user_id})
                    username = user.get("name") if user else "Unknown User"
                    phone_number = user.get("mobile_number") if user else "Unknown Number"

                # Aggregate dishes for individual orders
                ordered_dishes = cart.get("ordered_dishes", [])
                for dish in ordered_dishes:
                    dishes.append({
                        "dish_id": dish.get("dish_id"),
                        "name": dish.get("name"),
                        "variant": dish.get("variant"),
                        "size": dish.get("size"),
                        "quantity": dish.get("quantity"),
                        "price": dish.get("price"),
                        "total": dish.get("total"),
                        "dish_img_url": dish.get("dish_img_url"),
                        "discount": dish.get("total_discount")
                    })

            # Prepare the order details
            order_details = {
                "bill_no": order.get("bill_no"),
                "username": username,
                "phone_number": phone_number,
                "date": created_on_dt.strftime("%d/%m/%Y") if created_on_dt else "Unknown Date",
                "time": created_on_dt,
                "table_number": order.get('table_number'),
                "order_no": order.get('order_no'),
                "payment_method": order.get("payment_method"),
                "payment_status": order.get("payment_status"),
                "amount": order.get("amount", {}),
                "dishes": dishes
            }

            return JsonResponse(order_details, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({'message': 'Invalid request method! Only GET is allowed.'}, status=405)


@csrf_exempt
def update_order_status(request):

    if request.method == "PUT":
        try:
            # 1. Parse the JSON body
            body_unicode = request.body.decode('utf-8')
            body_data = json.loads(body_unicode) if body_unicode else {}

            order_id = body_data.get("order_id")
            new_status = body_data.get("new_status")
            payment_status = body_data.get("payment_status")

            if not order_id:
                return JsonResponse({
                    "message": "order_id is required."
                }, status=400)

            # 2. Reference your collection
            user_order_collection = db["UserOrder"]

            # 3. Find the order
            existing_order = user_order_collection.find_one({"_id": order_id})
            if not existing_order:
                return JsonResponse({
                    "message": f"Order with ID '{order_id}' not found."
                }, status=404)

            if new_status:
                # 4. Update the order's status
                user_order_collection.update_one(
                    {"_id": order_id},
                    {
                        "$set": {
                            "status": new_status,
                            "updated_on": datetime.utcnow().isoformat()  # or local time if needed
                        }
                    }
                )
            if payment_status:
                # 4. Update the order's status
                user_order_collection.update_one(
                    {"_id": order_id},
                    {
                        "$set": {
                            "payment_status": payment_status,
                            "updated_on": datetime.utcnow().isoformat()  # or local time if needed
                        }
                    }
                )

            return JsonResponse({
                "message": f"Order '{order_id}' status updated successfully."
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON format."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse(
            {"message": "Invalid request method. Only PUT is allowed."},
            status=405
        )


@csrf_exempt
def get_received_orders(request):
    if request.method == "GET":
        try:
            restro_id = request.GET.get('restro_id')
            status = request.GET.get('status', 'Received')  # Default to 'Received' if not specified

            if not restro_id:
                return JsonResponse(
                    {"message": "restro_id query parameter is required"},
                    status=400
                )
            if status not in ['Pending','Received', 'Completed']:
                return JsonResponse(
                    {"message": "Invalid status. Only 'Received' or 'Completed' or Pending are allowed."},
                    status=400
                )

            # Calculate today's earnings using ISO string comparisons
            today = date.today()
            start_datetime_today = datetime.combine(today, datetime.min.time())  # start of today
            end_datetime_today = start_datetime_today.replace(hour=23, minute=59, second=59)  # end of today
            
            start_today_iso = start_datetime_today.isoformat()  # start of today in ISO string
            end_today_iso = end_datetime_today.isoformat()  # end of today in ISO string

            # MongoDB Aggregation Pipeline
            user_order_collection = db["UserOrder"]
            cart_collection = db["Cart"]
            group_data_collection = db["GroupData"]
            user_data_collection = db["UserData"]

            # Aggregation query to filter orders based on status, restaurant, and today's date range
            orders = list(user_order_collection.aggregate([
                {"$match": {
                    "status": status,
                    "restro_id": restro_id,
                    # "payment_status": payment_status,
                    "created_on": {"$gte": start_today_iso, "$lte": end_today_iso}  # Compare with today's ISO range
                }},
                # Optionally, sort by created_on to get the latest order first
                {"$sort": {"created_on": DESCENDING}}
            ]))

            if not orders:
                return JsonResponse(
                    {"message": f"No orders found"})

            results = []

            for order in orders:
                _id = order.get("_id")
                table_number = order.get("table") or order.get("table_number")
                cart_id = order.get("cart_id")
                floor_name = order.get("floor_name")
                status = order.get("status")
                payment_method = order.get("payment_method")
                payment_status = order.get("payment_status")
                group_id = order.get("group_id")
                user_id = order.get("user_id")  
                created_on = order.get("created_on")

                cart_doc = cart_collection.find_one({"_id": cart_id})
                if not cart_doc:
                    continue

                dish_list = []
                username = "Unknown"
                phone_number = "Unknown"

                # Process group order
                if group_id:
                    group_dish_sets = cart_doc.get("group_members", [])
                    for group_item in group_dish_sets:
                        nested_dishes = group_item.get("ordered_dishes", [])
                        for dish in nested_dishes:
                            dish_list.append({
                                "dish_name": dish.get("name"),
                                "quantity": dish.get("quantity")
                            })

                    group_doc = group_data_collection.find_one({"_id": group_id})
                    if group_doc:
                        host_user_id = None
                        for member in group_doc.get("group_members", []):
                            if member.get("role") == "host":
                                host_user_id = member.get("user_id")
                                break

                        if host_user_id:
                            host_user = user_data_collection.find_one({"_id": host_user_id})
                            if host_user:
                                username = host_user.get("name", "Unknown Host")
                                phone_number = host_user.get("mobile_number", "Unknown Number")

                # Process individual order
                else:
                    individual_dishes = cart_doc.get("ordered_dishes", [])
                    for dish in individual_dishes:
                        dish_list.append({
                            "dish_name": dish.get("name"),
                            "quantity": dish.get("quantity")
                        })

                    if user_id:
                        user_doc = user_data_collection.find_one({"_id": user_id})
                        if user_doc:
                            username = user_doc.get("name", "Unknown")
                            phone_number = user_doc.get("mobile_number", "Unknown")
                        else:
                            username = "Unknown"
                            phone_number = "Unknown"
                    else:
                        username = "Unknown"
                        phone_number = "Unknown"

                results.append({
                    "order_id": _id,
                    "table_number": table_number,
                    "floor_name": floor_name,
                    "status": status,
                    "payment_method": payment_method,
                    "payment_status": payment_status,
                    "username": username,
                    "phone_number": phone_number,
                    "dishes": dish_list,
                    "created_on": created_on
                })

            return JsonResponse({"data": results}, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse(
            {"message": "Invalid request method! Only GET is allowed."},
            status=405
        )
