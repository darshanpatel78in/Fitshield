from asyncio.log import logger
from datetime import datetime
import json
import logging
import pymongo

from fitshield_webapp.utils.format_validate import store_notification
from ...utils.generate_id import generate_order_id
from ...utils.logging_utils import get_logger
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import JsonResponse
from django.utils.timezone import now


def calculate_group_order_totals(ordered_dishes):
    # print(f"orderrrrrrrrrrrr: {ordered_dishes}")
    
    total_discount = 0.0
    grand_total_price = 0.0
    grand_total_quantity = 0
    
    for dish in ordered_dishes:
        discount = dish.get('discount', 0)
        if isinstance(discount, dict) and discount.get('full_discount', {}).get('discount_applied', False):
            discount_price = discount['full_discount'].get('discount_price', 0)
            current_price = discount['full_discount'].get('current_price', 0)
            total_discount += (current_price - discount_price) * dish['quantity']
        else:
            total_discount += 0
            
        grand_total_price += dish.get('price', 0) * dish.get('quantity', 0)
        # Calculate the grand total quantity
        grand_total_quantity += dish.get('quantity', 0)

    # Round the total discount to two decimal places
    total_discount = round(total_discount, 2)

    return total_discount, grand_total_price, grand_total_quantity


def calculate_individual_order_totals(ordered_dishes):
    total_discount = round(sum(
        sum(
            (discount.get("current_price", 0) - discount.get("discount_price", 0)) * dish["quantity"]
            for discount in dish.get("total_discount", {}).values()
            if isinstance(discount, dict) and discount.get("discount_applied", False)
        )
        for dish in ordered_dishes
    ), 2)

    grand_total_price = sum(dish["original_price"] * dish["quantity"] for dish in ordered_dishes)
    grand_total_quantity = sum(dish["quantity"] for dish in ordered_dishes)

    return total_discount, grand_total_price, grand_total_quantity

@csrf_exempt
def create_order(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            cart_id = data.get("cart_id")
            restro_id = data.get("restro_id")
            table_number = data.get("table_number")
            payment_status = data.get("payment_status")
            payment_method = data.get("payment_method")
            status = data.get("status", "Pending")
            group_id = data.get("group_id")
            user_id = data.get("user_id")
            floor_name = data.get("floor_name")  

            if not cart_id or not table_number or not restro_id:
                return JsonResponse({"error": "Missing required fields (cart_id, table, restro_id)"}, status=400)

            cart_collection = db["Cart"]
            restaurant_collection = db["RestroData"]
            orders_collection = db["UserOrder"]
            counter_collection = db["BillNumberCounter"]

            cart = cart_collection.find_one({"_id": cart_id})
            if not cart:
                return JsonResponse({"error": "Cart not found"}, status=404)

            restaurant = restaurant_collection.find_one({"_id": restro_id})
            if not restaurant:
                return JsonResponse({"error": "Restaurant not found"}, status=404)

            # Check if tax is already included
            taxes = restaurant.get("bank_details", {}).get("taxes", {})
            is_tax_included = taxes.get("is_tax_included", False)
            gst = float(taxes.get("SGST", "0%").strip('%')) + float(taxes.get("CGST", "0%").strip('%'))
            service_tax = float(taxes.get("service_charge", "0%").strip('%'))
            platform_fee = 0.0  

            # Group Orders
            if group_id:
                ordered_dishes = [
                    dish for member in cart.get("group_members", []) for dish in member.get("ordered_dishes", [])
                ]
                total_discount, grand_total_price, grand_total_quantity = calculate_group_order_totals(ordered_dishes)

            # Individual Orders
            else:
                ordered_dishes = cart.get("ordered_dishes", [])
                total_discount, grand_total_price, grand_total_quantity = calculate_individual_order_totals(ordered_dishes)
                
            # total_discount = round(sum(
            #     sum(
            #         (discount.get("current_price", 0) - discount.get("discount_price", 0)) * dish["quantity"]
            #         for discount in dish.get("total_discount", {}).values()
            #         if isinstance(discount, dict) and discount.get("discount_applied", False)
            #     )
            #     for dish in ordered_dishes
            # ), 2)

            # grant price and quantity
            grand_total_price = sum(dish["original_price"] * dish["quantity"] for dish in ordered_dishes)
            # print(f"grand_total_price: {grand_total_price}")
            
            grand_total_quantity = sum(dish["quantity"] for dish in ordered_dishes)

            # Calculate tax amounts
            #service_tax_amount = (service_tax / 100) * grand_total_price

            # Adjust total price based on tax inclusion
            gst_count = 100 + gst
            if is_tax_included:
                #gst_count = 100 + gst
                gst_amount = grand_total_price - (grand_total_price * 100 / gst_count)
                subtotal = grand_total_price - gst_amount
                service_tax_amount = (service_tax / 100) * grand_total_price
                # grand_total_price = (100 * grand_total_price) / gst_count  # Remove GST if included
                # payable_amount = round(subtotal + service_tax_amount - total_discount, 2)

            else:
                gst_amount = grand_total_price * gst_count / 100
                subtotal = grand_total_price
                service_tax_amount = (subtotal+gst_amount) * service_tax / 100
                # grand_total_price = grand_total_price + (grand_total_price * gst / 100)
                # payable_amount = round(subtotal  + service_tax_amount - total_discount, 2)
            payable_amount = round(subtotal + gst_amount + service_tax_amount - total_discount ,2)
            #gst_amount = (gst / 100) * grand_total_price
            #grand_total_price = round(grand_total_price, 2)
            #subtotal = grand_total_price
            total_quantity = grand_total_quantity


            # Generate Order ID
            current_date = datetime.utcnow().strftime("%Y-%m-%d")

            # Increment daily order counter
            updated_counter = counter_collection.find_one_and_update(
                {"date": current_date},
                {"$inc": {"current_value": 1}},
                upsert=True,
                return_document=pymongo.ReturnDocument.AFTER
            )
            order_no = updated_counter["current_value"]

            # Increment global bill counter
            global_counter = counter_collection.find_one_and_update(
                {"_id": "bill_number_counter"},
                {"$inc": {"current_value": 1}},
                upsert=True,
                return_document=pymongo.ReturnDocument.AFTER
            )
            bill_no = global_counter["current_value"]

            order_id = generate_order_id()

            # **Prepare Order Data**
            order_data = {
                "_id": order_id,
                "restro_id": restro_id,
                "order_no": order_no,
                "bill_no": bill_no,
                "user_id": user_id if user_id else None,
                "group_id": group_id if group_id else None,
                "cart_id": cart_id,
                "floor_name": floor_name if floor_name else None,  # Store floor_name safely
                "table_number": str(table_number),
                "status": status,
                "amount": {
                    "subtotal": subtotal,
                    "service_tax": service_tax,  # percentage
                    "gst": gst, # percentage
                    "discount_amount": total_discount,
                    "platform_fee": platform_fee,
                    "payable_amount": payable_amount
                },
                "payment_method" : payment_method,
                "payment_status": payment_status,
                "total_quantity": total_quantity,
                "created_on": datetime.utcnow().isoformat(),
                "updated_on": datetime.utcnow().isoformat()
            }
            orders_collection.insert_one(order_data)

            cart_collection.update_one(
                {"_id": cart_id},
                {"$set": {"is_order_completed": True}}
            )
            # Send Order Notification
            store_notification(
                collection=db["Notification"],
                restro_id=restro_id,
                notification_type="Order",
                event="Order Placed",
                description=f"New order #{order_no} has been placed.",
                details={"order_id": order_id, "total_amount": payable_amount},
                expiry_hours=24  
            )

            # print("Notification Sent:", store_notification)

            return JsonResponse({
                "message": "Order created successfully.",
                "order_id": order_id,
                "order_no": order_no,
                "bill_no": bill_no,
                "status": status,
                "payment_status": payment_status,
                "amount": {
                    "subtotal": subtotal,
                    "service_tax": service_tax,
                    "gst": gst,
                    "discount_amount": total_discount,
                    "platform_fee": platform_fee,
                    "payable_amount": payable_amount
                },
                "total_quantity": total_quantity
            }, status=201)

        except Exception as e:
            return JsonResponse({"error": f"Error creating order: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid HTTP method, only POST is allowed"}, status=405)

# @csrf_exempt
# def delete_order(request):
#     if request.method == "DELETE":

#         data = json.loads(request.body)
#         order_id = data.get("order_id")

#         if not order_id:
#             return JsonResponse({"error": "Order ID is required"}, status=400)

#         orders_collection = db["UserOrder"]

#         order_result = orders_collection.delete_one({"_id": order_id})

#         if order_result.deleted_count == 0:
#             return JsonResponse({"error": "Order not found"}, status=404)

#         orders_collection.delete_many({"_id": order_id})

#         return JsonResponse({"message": "Order deleted successfully"}, status=200)

# @csrf_exempt
# def list_order(request):
#     if request.method == "GET":

#         data = json.loads(request.body)

#         user_id = data.get("user_id")

#         if not user_id:
#             return JsonResponse({"error": "User ID is required"}, status=400)

#         orders_collection = db["UserOrder"]
#         orders = list(orders_collection.find({"user_id": user_id}))
#         if not orders:
#             return JsonResponse({"error": "No orders found for the user"}, status=404)

#         orders_list = {
#             "user_id": user_id,
#             "orders": [
#                 {
#                     "order_id": order["_id"],
#                     "status": order["status"],
#                     "payable_amount": order["amount"]["payable_amount"],
#                     "created_on": order["created_on"],
#                 }
#                 for order in orders
#             ]
#         }
#         return JsonResponse(orders_list, safe=False, status=200)

# @csrf_exempt
# def update_order(request):
#     if request.method == "PUT":
#         try:

#             data = json.loads(request.body)
#             order_id = data.get("order_id")
#             status = data.get("status")

#             if not order_id or not status:
#                 return JsonResponse({"error": "Invalid input"}, status=400)

#             orders_collection = db["UserOrder"]
#             result = orders_collection.update_one(
#                 {"_id": order_id},
#                 {"$set": {"status": status, "updated_on": now()}}
#             )

#             if result.matched_count == 0:
#                 return JsonResponse({"error": "Order not found"}, status=404)

#             return JsonResponse({"message": "Order updated successfully"}, status=200)

#         except Exception as e:
#             # print("Error in update_order:", str(e))
#             return JsonResponse({"error": "Internal Server Error"}, status=500)
#     else:
#         return JsonResponse({"error": "Invalid HTTP method"}, status=405)

@csrf_exempt
def confirm_order(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order_id = data.get("order_id")

            if not order_id:
                return JsonResponse({"error": "Order ID is required."}, status=400)

            orders_collection = db["UserOrder"]
            order = orders_collection.find_one({"_id": order_id})

            if not order:
                return JsonResponse({"error": f"Order with ID '{order_id}' not found."}, status=404)

            if order.get("status") == "Confirmed":
                return JsonResponse({"message": "Order is already confirmed."}, status=200)

            orders_collection.update_one(
                {"_id": order_id},
                {"$set": {"status": "Confirmed"}}
            )

            return JsonResponse({
                "message": "Order confirmed successfully.",
                "order_id": order_id,
                "status": "Confirmed"
            }, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Use POST."}, status=405)

