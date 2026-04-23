from asyncio.log import logger
from datetime import datetime
import json
import uuid
import logging

from fitshield_webapp.utils.format_validate import two_decimals
from fitshield_webapp.view.restro.save_json import save_json_to_file
from ...utils.logging_utils import get_logger
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import JsonResponse
import pytz
from datetime import datetime

ist_timezone = pytz.timezone("Asia/Kolkata")

def convert_to_ist(timestamp):
    if timestamp:
        try:
            # Convert from UTC to IST
            utc_time = datetime.fromisoformat(str(timestamp)).replace(tzinfo=pytz.utc)
            ist_time = utc_time.astimezone(ist_timezone)
            return ist_time.isoformat()
        except ValueError:
            print(f"Invalid timestamp format: {timestamp}")
    return None


restaurantmenudata_collection= db["RestaurantMenuData"]


@csrf_exempt
def add_to_cart(request):
    try:
        if request.method != "PUT":
            return JsonResponse({"error": "Invalid HTTP method, only PUT is allowed"}, status=405)

        data = json.loads(request.body)
        cart_id = data.get("cart_id")
        group_id = data.get("group_id")
        user_id = data.get("user_id")
        restro_id = data.get("restro_id")
        dish_id = data.get("dish_id")
        dish_type = data.get("dish_type", "").lower()
        dish_size = data.get("dish_size", "").lower()
        quantity_to_add = data.get("quantity")
        role = data.get("role", None)
        # print(f"user's role is:{role}")

        if quantity_to_add is None or not isinstance(quantity_to_add, int) or quantity_to_add <= 0:
            return JsonResponse({"error": "Invalid or missing quantity"}, status=400)
        
        if not cart_id or not restro_id or not dish_id or quantity_to_add <= 0:
            return JsonResponse({"error": "Invalid input: cart_id, restro_id, dish_id, and quantity are required"}, status=400)

        cart_collection = db["Cart"]
        restaurant_menu_collection = db["RestaurantMenuData"]
        userdata_collection = db["UserData"]

        user = userdata_collection.find_one({"_id": user_id}, {"name": 1, "_id": 0})
        user_name = user["name"] if user and "name" in user else "Unknown"

        cart = cart_collection.find_one({"_id": cart_id})
        if not cart:
            return JsonResponse({"error": "Cart not found"}, status=404)

        dish = restaurant_menu_collection.find_one(
            {"_id": restro_id, "menu._id": dish_id},
            {"menu.$": 1}
        )

        if not dish:
            return JsonResponse({"error": "Dish not found in the specified restaurant"}, status=404)

        if cart.get("is_lock", False):
            return JsonResponse({"error": "Cart is locked. Cannot add items."}, status=403)
        
        dish_details = dish["menu"][0]
        # save_json_to_file(dish_details, "dishes_output", "dishh_details.json")
        
        dish_img_url = dish_details.get("dish_img_url","")
        variant_data = dish_details.get("dish_variants", {}).get(dish_type, {}).get(dish_size)
        if not variant_data:
            return JsonResponse({"error": f"Dish variant ({dish_type}, {dish_size}) not found"}, status=400)

        # ***************** discount details*****************
        discount_variant = dish_details.get("discount") if dish_details.get("discount") else {}
        # save_json_to_file(discount_variant, "dishes_output", "discount_variant.json")

        discount_data = dish_details.get("discount", {}).get(f"{dish_size}_discount", {})
        current_price = two_decimals(variant_data.get("price", 0))
        discount_price = two_decimals(discount_data.get("discount_price", current_price)) if discount_data.get("discount_applied", False) else current_price
        
        price = discount_price
        total = two_decimals(price * quantity_to_add)
        dish_discount = two_decimals((current_price - price) * quantity_to_add)

        # save_json_to_file(cart, "dishes_output", "cart.json")

        # If group order
        if group_id:
            added_by = data.get("added_by")
            user_id = data.get("added_by")

            # user_entry = next((entry for entry in cart.get("group_members", []) if entry.get("added_by") == added_by), None)
            user_entry = next((entry for entry in cart.get("group_members", []) if entry.get("user_id") == user_id), None)

            if user_entry:

                if not user_entry["ordered_dishes"]:
                    user_entry["ordered_dishes"] = []

                updated = False
                for dish_entry in user_entry["ordered_dishes"]:
                    if dish_entry["dish_id"] == dish_id and dish_entry["variant"] == dish_type and dish_entry["size"] == dish_size:
                        dish_entry["quantity"] += quantity_to_add
                        dish_entry["total"] = two_decimals(dish_entry["quantity"] * price)
                        # dish_entry["discount"] = two_decimals((current_price - discount_price) * dish_entry["quantity"])
                        dish_entry["discount"] = discount_variant
                        updated = True
                        break

                if not updated:
                    user_entry["ordered_dishes"].append({
                        "dish_id": dish_id,
                        "name": dish_details["dish_name"],
                        "is_veg": True if dish_details["food_category"] == "Vegetarian" else False,
                        "variant": dish_type,
                        "size": dish_size,
                        "quantity": quantity_to_add,
                        "price": price,
                        "original_price": current_price,
                        "total": total,
                        "dish_img_url": dish_img_url,
                        "discount": discount_variant
                    })

                user_entry.update({
                    "user_id": user_id,
                    "role": role,
                    "name": user_name,
                    "user_quantity": sum(d["quantity"] for d in user_entry["ordered_dishes"]),
                    "user_price": two_decimals(sum(d["total"] for d in user_entry["ordered_dishes"])),
                    "added_by": user_id,
                })

                cart_collection.update_one(
                    {"_id": cart_id, "group_members.user_id": user_id},
                    {"$set": {
                        "group_members.$.user_quantity": user_entry["user_quantity"],
                        "group_members.$.user_price": user_entry["user_price"],
                        "group_members.$.added_by": user_entry["added_by"],
                        "group_members.$.ordered_dishes": user_entry["ordered_dishes"]
                    }}
                )
                
            else:
                # save to database
                new_user_entry = {
                    "user_id": user_id,
                    "name": user_name,
                    "role": role,
                    "user_quantity": quantity_to_add,
                    "user_price": total,
                    "added_by": added_by,
                    "ordered_dishes": [{
                        "dish_id": dish_id,
                        "name": dish_details["dish_name"],
                        "is_veg": True if dish_details["food_category"] == "Vegetarian" else False,
                        "variant": dish_type,
                        "size": dish_size,
                        "quantity": quantity_to_add,
                        "price": price,
                        "original_price": current_price,
                        "total": total,
                        "dish_img_url": dish_img_url,
                        "discount": discount_variant
                    }]
                }

                cart_collection.update_one(
                    {"_id": cart_id},
                    {"$push": {"group_members": new_user_entry}}
                )

            cart = cart_collection.find_one({"_id": cart_id})   

            # Calculate grand total discount
            # grand_total_discount = round(sum(
            #     sum(
            #         (discount["current_price"] - discount["discount_price"]) * d["quantity"]
            #         for key, discount in d.get("discount", {}).items()
            #         if isinstance(discount, dict) and discount.get("discount_price", 0) > 0 and discount.get("discount_applied", False)  # Ensure valid discount and applied status
            #     )
            #     for u in cart.get("group_members", [])
            #     for d in u.get("ordered_dishes", [])
            # ), 2)

            grand_total_discount = round(sum(
                sum(
                    (discount.get("current_price", 0) - discount.get("discount_price", 0)) * d["quantity"]
                    for key, discount in (d.get("discount", {}) if isinstance(d.get("discount", {}), dict) else {}).items()
                    if isinstance(discount, dict) and discount.get("discount_price", 0) > 0 and discount.get("discount_applied", False)
                )
                for u in cart.get("group_members", [])
                for d in u.get("ordered_dishes", [])
            ), 2)

            # Calculate grand total quantity
            grand_total_quantity = sum(
                int(d.get("quantity", 0))  # Ensure it's always an integer
                for u in cart.get("group_members", [])
                for d in u.get("ordered_dishes", [])
            )

            # Calculate grand total price
            grand_total_price = two_decimals(sum(
                d.get("total", 0)
                for u in cart.get("group_members", [])
                for d in u.get("ordered_dishes", [])
            ))

            cart_collection.update_one(
                {"_id": cart_id},
                {"$set": {
                    "grand_total_quantity": grand_total_quantity,
                    "grand_total_price": grand_total_price,
                    "grand_total_discount": grand_total_discount 
                }}
            )

        else:
            updated = False
            for i, cart_dish in enumerate(cart.get("ordered_dishes", [])):
                if (
                    cart_dish["dish_id"] == dish_id
                    and cart_dish["variant"] == dish_type
                    and cart_dish["size"] == dish_size
                ):
                    
                    cart["ordered_dishes"][i]["quantity"] += quantity_to_add
                    cart["ordered_dishes"][i]["total"] = two_decimals(cart["ordered_dishes"][i]["quantity"] * price)

                    updated = True
                    # print(f"Updated cart: {cart}")

                    cart_collection.update_one(
                        {"_id": cart_id},
                        {"$set": {"ordered_dishes": cart["ordered_dishes"]}}
                    )
                    break  

            if not updated:
                # print("Creating new dish entry...")
                new_dish = {
                    "dish_id": dish_id,
                    "name": dish_details["dish_name"],
                    "is_veg": True if dish_details["food_category"] == "Vegetarian" else False,
                    "variant": dish_type,
                    "size": dish_size,
                    "quantity": quantity_to_add,
                    "price": price,
                    "total": total,
                    "original_price": current_price,
                    "dish_img_url": dish_img_url,
                    "total_discount": discount_variant
                }
                cart_collection.update_one(
                    {"_id": cart_id},
                    {"$push": {"ordered_dishes": new_dish}}
                )

            cart = cart_collection.find_one({"_id": cart_id})
            grand_total_quantity = sum(dish["quantity"] for dish in cart.get("ordered_dishes", []))
            grand_total_price = two_decimals(sum(
                dish["price"] * dish["quantity"] for dish in cart.get("ordered_dishes", [])
            ))


            # save_json_to_file(cart, "dishes_output", "cartuu.json")

            grand_total_discount = round(sum(
                sum(
                    (discount.get("current_price", 0) - discount.get("discount_price", 0)) * dish["quantity"]
                    for discount in dish.get("total_discount", {}).values()
                    if isinstance(discount, dict) and discount.get("discount_price", 0) > 0 and discount.get("discount_applied", False)
                )
                for dish in cart.get("ordered_dishes", [])
            ), 2)

            cart_collection.update_one(
                {"_id": cart_id},
                {"$set": {
                    "grand_total_discount": grand_total_discount,
                    "grand_total_price": grand_total_price,
                    "grand_total_quantity": grand_total_quantity
                }}
            )

        return JsonResponse({"message": "Dish added to cart successfully"}, status=201)

    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

@csrf_exempt
def update_dish_quantity(request):
    if request.method != "PUT":
        return JsonResponse({"error": "Invalid request method. Use PUT."}, status=405)

    try:
        data = json.loads(request.body)
        
        cart_id = data.get("cart_id")
        dishes = data.get("dishes")  
        group_id = data.get("group_id")  
        user_id = data.get("user_id")  
        updated_by = data.get("updated_by")  
        added_by = data.get("added_by")  

        cart_collection = db["Cart"]

        if not cart_id or not dishes:
            return JsonResponse({"error": "cart_id and dishes are required."}, status=400)

        if not user_id and not group_id:
            return JsonResponse({"error": "user_id or group_id is required."}, status=400)

        if group_id and not updated_by:
            return JsonResponse({"error": "updated_by is required for group orders."}, status=400)

        # Fetch Cart
        cart = cart_collection.find_one({"_id": cart_id})
        if not cart:
            return JsonResponse({"error": "Cart not found."}, status=404)

        # **GROUP ORDER HANDLING**
        if group_id:
            if cart.get("group_id") != group_id:
                return JsonResponse({"error": "Cart does not belong to the specified group."}, status=403)

            group_members = cart.get("group_members", [])
            host_id = next((m["user_id"] for m in group_members if m["role"] == "host"), None)

            if not host_id:
                return JsonResponse({"error": "Group host not found."}, status=404)

            for dish_entry in dishes:
                dish_id = dish_entry.get("dish_id")
                quantity = dish_entry.get("quantity")
                dish_size = dish_entry.get("dish_size", "").lower()
                dish_type = dish_entry.get("dish_type", "").lower()
                added_by = dish_entry.get("added_by")

                if not dish_id or quantity is None:
                    return JsonResponse({"error": "Each dish must have dish_id and quantity."}, status=400)

                try:
                    quantity = int(quantity)
                except ValueError:
                    return JsonResponse({"error": "Quantity must be a valid integer."}, status=400)

                user_entry = next((m for m in group_members if m["user_id"] == added_by), None)
                if not user_entry:
                    return JsonResponse({"error": "User who added the dish not found in group."}, status=403)

                # Validate if the dish exists in the correct user's ordered dishes
                matching_dish = next(
                    (dish for dish in user_entry.get("ordered_dishes", [])
                    if dish["dish_id"] == dish_id
                    and dish["size"].lower() == dish_size.lower()
                    and dish["variant"].lower() == dish_type.lower()), 
                    None
                )
                if not matching_dish:
                    return JsonResponse({
                        "error": f"Dish with ID '{dish_id}' and size '{dish_size}' and variant '{dish_type}' not found in the cart."
                    }, status=400)

                # Find the host ID
                host_id = next((m["user_id"] for m in group_members if m["role"] == "host"), None)

                # Restriction: Members cannot update dishes added by the host
                if added_by == host_id and updated_by != host_id:
                    return JsonResponse({"error": "Members cannot update dishes added by the host."}, status=403)
                # print(f"host_id: {host_id}, added_by: {added_by}, updated_by: {updated_by}")

                if host_id == updated_by or added_by == updated_by:
                    for dish in user_entry.get("ordered_dishes", []):
                        if dish["dish_id"] == dish_id and dish["size"].lower() == dish_size and dish["variant"].lower() == dish_type:
                            price = dish.get("price", 0)

                            if quantity == 0:
                                cart_collection.update_one(
                                    # {"_id": cart_id, "group_members.user_id": updated_by},
                                     {"_id": cart_id, "group_members.user_id": added_by, "group_members.ordered_dishes.dish_id": dish_id},
                                    {"$pull": {"group_members.$.ordered_dishes": {"dish_id": dish_id, "size": dish_size, "variant": dish_type}}}
                                )
                            else:
                                total = quantity * price
                                cart_collection.update_one(
                                    {"_id": cart_id, "group_members.user_id": added_by, "group_members.ordered_dishes.dish_id": dish_id},
                                    {"$set": {
                                        "group_members.$.ordered_dishes.$[elem].quantity": quantity,
                                        "group_members.$.ordered_dishes.$[elem].total": total,
                                        "group_members.$.ordered_dishes.$[elem].discount": dish.get("discount", {})
                                    }},
                                    array_filters=[{"elem.dish_id": dish_id, "elem.size": dish_size, "elem.variant": dish_type}]
                                )

                                # cart_collection.update_one(
                                #     {
                                #         "_id": cart_id
                                #     },
                                #     {
                                #         "$set": {
                                #             "group_members.$[member].ordered_dishes.$[elem].quantity": quantity,
                                #             "group_members.$[member].ordered_dishes.$[elem].total": total,
                                #             "group_members.$[member].ordered_dishes.$[elem].discount": dish.get("discount", {})
                                #         }
                                #     },
                                #     array_filters=[
                                #         {"member.user_id": added_by},  # Match group member
                                #         {"elem.dish_id": dish_id, "elem.size": dish_size, "elem.variant": dish_type}  # Match dish inside ordered_dishes
                                #     ]
                                # )


                    # **Update User Totals**
                    updated_user_entry = cart_collection.find_one(
                        {"_id": cart_id, "group_members.user_id": updated_by},
                        {"group_members.$": 1}
                    )

                    if updated_user_entry:
                        user_entry = updated_user_entry["group_members"][0]
                        user_entry["user_quantity"] = sum(d["quantity"] for d in user_entry.get("ordered_dishes", []))
                        user_entry["user_price"] = sum(d["total"] for d in user_entry.get("ordered_dishes", []))

                        cart_collection.update_one(
                            {"_id": cart_id, "group_members.user_id": updated_by},
                            {"$set": {
                                "group_members.$.user_quantity": user_entry["user_quantity"],
                                "group_members.$.user_price": user_entry["user_price"]
                            }}
                        )

            # Update Group Totals
            cart = cart_collection.find_one({"_id": cart_id})
            grand_total_quantity = sum(user.get("user_quantity", 0) for user in cart.get("group_members", []))
            grand_total_price = sum(user.get("user_price", 0) for user in cart.get("group_members", []))

            # **Calculate Grand Total Discount**
            cart = cart_collection.find_one({"_id": cart_id})

            # grand_total_discount = round(sum(
            #     sum(
            #         (d["discount"][key]["current_price"] - d["discount"][key]["discount_price"]) * d["quantity"]
            #         for key in d["discount"]
            #         if isinstance(d["discount"], dict)  # Ensure discount is a dictionary
            #     ) if isinstance(d.get("discount"), dict) else (d["discount"] * d["quantity"] if isinstance(d.get("discount"), (int, float)) else 0)
            #     for u in cart.get("group_members", [])
            #     for d in u.get("ordered_dishes", [])
            # ), 2)

            grand_total_discount = round(sum(
                sum(
                    (d["discount"][key]["current_price"] - d["discount"][key]["discount_price"]) * d["quantity"]
                    for key in d["discount"]
                    if isinstance(d["discount"], dict) and d["discount"][key].get("discount_applied", True)  # Ensure discount is actually applied
                ) if isinstance(d.get("discount"), dict) else (d["discount"] * d["quantity"] if isinstance(d.get("discount"), (int, float)) and d["discount"] > 0 else 0)
                for u in cart.get("group_members", [])
                for d in u.get("ordered_dishes", [])
            ), 2)
            

            # print(f"grand_total_discount: {grand_total_discount}")

            cart_collection.update_one(
                {"_id": cart_id},
                {"$set": {
                    "grand_total_quantity": grand_total_quantity,
                    "grand_total_price": grand_total_price,
                    "grand_total_discount": grand_total_discount
                }}
            )
            # print(f"group discount: {grand_total_discount}")
            return JsonResponse({"message": "Dish quantities updated successfully in group cart."}, status=200)

        # **INDIVIDUAL CART HANDLING**
        else:
            for update_dish in dishes:
                dish_id = update_dish.get("dish_id")
                quantity = update_dish.get("quantity")
                dish_size = update_dish.get("dish_size", "").lower()
                dish_type = update_dish.get("dish_type", "").lower()

                if not dish_id or quantity is None:
                    return JsonResponse({"error": "Each dish must have dish_id and quantity."}, status=400)

                cart = cart_collection.find_one({"_id": cart_id})
                if not cart:
                    return JsonResponse({"error": "Cart not found."}, status=404)
        
                cart_dishes = cart.get("ordered_dishes", [])
                # print(f"cart_dishes:{cart_dishes}")

                matched_dish = next((d for d in cart_dishes if d["dish_id"] == dish_id and d["size"].lower() == dish_size and d["variant"].lower() == dish_type), None)
                if not matched_dish:
                    continue
                # print(f"matched_dish:{matched_dish}")
                
                try:
                    quantity = int(quantity)
                except ValueError:
                    return JsonResponse({"error": "Quantity must be a valid integer."}, status=400)

                price = matched_dish.get("price", 0)
                total = quantity * price

                if quantity == 0:
                    cart_collection.update_one(
                        {"_id": cart_id},
                        {"$pull": {"ordered_dishes": {"dish_id": dish_id, "size": dish_size, "variant": dish_type}}}
                    )
                else:
                    cart_collection.update_one(
                        {
                            "_id": cart_id
                        },
                        {
                            "$set": {
                                "ordered_dishes.$[elem].quantity": quantity,
                                "ordered_dishes.$[elem].total": total,
                                "ordered_dishes.$[elem].discount": matched_dish.get("discount", 0)
                            }
                        },
                        array_filters=[{"elem.dish_id": dish_id, "elem.variant": dish_type, "elem.size": dish_size}]
                    )




            cart = cart_collection.find_one({"_id": cart_id})
            # Recalculate totals
            total_quantity = sum(d["quantity"] for d in cart.get("ordered_dishes", []))
            total_price = sum(d["original_price"] for d in cart.get("ordered_dishes", []))
            # print(f"total_priceeeeeeeeeeee: {total_price}")
            
            # grand_total_discount = round(sum(
            #     sum(
            #         (discount["current_price"] - discount["discount_price"]) * dish["quantity"]
            #         for discount in dish.get("total_discount", {}).values()
            #         if isinstance(discount, dict)
            #     )
            #     for dish in cart.get("ordered_dishes", [])
            # ), 2)

            grand_total_discount = round(sum(
                sum(
                    (discount["current_price"] - discount["discount_price"]) * dish["quantity"]
                    for discount in dish.get("total_discount", {}).values()
                    if isinstance(discount, dict) and discount["discount_applied"]
                )
                for dish in cart.get("ordered_dishes", [])
            ), 2)

            # print(f"grand_total_discount: {grand_total_discount}")

            grand_total_price = round(sum(dish["price"] * dish["quantity"] for dish in cart.get("ordered_dishes", [])), 2)
            grand_total_quantity = sum(dish["quantity"] for dish in cart.get("ordered_dishes", []))

            # Update the cart once with all computed totals
            cart_collection.update_one(
                {"_id": cart_id},
                {"$set": {
                    "total_quantity": total_quantity,
                    "total_price": total_price,
                    "grand_total_discount": grand_total_discount,
                    "grand_total_price": grand_total_price,
                    "grand_total_quantity": grand_total_quantity
                }}
            )

            return JsonResponse({"message": "Dish quantities updated successfully in individual cart."}, status=200)

    except Exception as e:
        return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)


@csrf_exempt
def view_individual_cart(request):
    if request.method == 'GET':
        try:
            user_id = request.GET.get('user_id')
            cart_id = request.GET.get("cart_id")  

            cart_collection = db["Cart"]
            menu_collection = db["RestaurantMenuData"]

            if not cart_id or not user_id:
                return JsonResponse({"error": "Both cart_id and user_id are required"}, status=400)

            cart_data = cart_collection.find_one({"_id": cart_id, "user_id": user_id}) 

            for dish in cart_data.get("ordered_dishes", []):  
                dish_data = menu_collection.find_one(
                            {"menu._id": dish["dish_id"]},  
                            {"menu.$": 1}  
                        )
                if dish_data and "menu" in dish_data and len(dish_data["menu"]) > 0:
                    menu_item = dish_data["menu"][0]
                    dish["dish_img_url"] = menu_item.get("dish_img_url", "")
                else:
                    dish["dish_img_url"] = ""

            if not cart_data:
                return JsonResponse({"error": "No cart data found for the given cart_id and user_id"}, status=404)

            # save_json_to_file(cart_data,"dishes_output","cart_datatttt.json")
            return JsonResponse(cart_data, safe=False, status=200)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Use GET."}, status=405)


@csrf_exempt
def view_group_cart(request):
    if request.method == 'GET':
        try:
            user_id = request.GET.get('user_id')
            group_id = request.GET.get('group_id')
            role = request.GET.get('role')

            cart_collection = db["Cart"]
            menu_collection = db["RestaurantMenuData"]
            userdata_collection = db["UserData"]
            group_data_collection = db["GroupData"]

            user = userdata_collection.find_one({"_id": user_id}, {"name": 1, "_id": 0})
            user_name = user["name"] if user and "name" in user else "Unknown"

            if group_id:
                group_cart = cart_collection.find({"group_id": group_id})
                group_cart = list(group_cart)
                
                if not group_cart:
                    return JsonResponse({"error": "No cart data found for the given group_id"}, status=404)

                group_cart = group_cart[0]
                # save_json_to_file(group_cart, "dishes_output", "group_cart.json" )
                
                # Check if user already exists in group_members
                group_members = group_cart.get("group_members", [])
                print(group_members)

                is_order_completed = group_cart.get("is_order_completed")

                # Check if the user is removed
                # removed_users = group_cart.get("removed_users", [])
                # if user_id in removed_users:
                #     return JsonResponse({"error": "User was removed from the group"}, status=403)

                # user_exists = any(member["user_id"] == user_id for member in group_members)
                # existing_user_note = next((member.get("user_note", "") for member in group_members if member["user_id"] == user_id), "")
               
                # If user is not in the group, add them with default values
                # if not user_exists:
                #     new_user_entry = {
                #         "user_id": user_id,
                #         "role": role,
                #         "name": user_name,
                #         "user_quantity": 0,
                #         "user_price": 0,
                #         "added_by": user_id,
                #         "ordered_dishes": [],
                #         "user_note": existing_user_note
                #     }
                    
                #     cart_collection.update_one(
                #         {"group_id": group_id},
                #         {"$push": {"group_members": new_user_entry}}
                #     )
                    # Fetch updated group cart after adding user

                
                group_cart = cart_collection.find_one({"group_id": group_id})

                for user_entry in group_cart.get("group_members", []):
                    for dish in user_entry.get("ordered_dishes", []):
                        dish_data = menu_collection.find_one(
                            {"menu._id": dish["dish_id"]},
                            {"menu.$": 1}
                        )
                        if dish_data and "menu" in dish_data and len(dish_data["menu"]) > 0:
                            dish["dish_img_url"] = dish_data["menu"][0].get("dish_img_url", "")
                        else:
                            dish["dish_img_url"] = ""

                response_data = {
                    "group_id": group_cart.get("group_id"),
                    "restro_id": group_cart.get("restro_id"),
                    "is_lock": group_cart.get("is_lock"),
                    "is_order_completed": is_order_completed,
                    "grand_total_price": group_cart.get("grand_total_price", 0),
                    "grand_total_quantity": group_cart.get("grand_total_quantity", 0),
                    "grand_total_discount": group_cart.get("grand_total_discount", 0),
                    "group_members": group_cart.get("group_members", [])
                }

                return JsonResponse(response_data, safe=False, status=200)

            return JsonResponse({"error": "user_id or group_id is required"}, status=400)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Use GET."}, status=405)



@csrf_exempt
def add_restaurant_notes(request):
    if request.method == "PUT":
        try:
            data = json.loads(request.body)

            user_id = data.get("user_id")  # userid for both individual and group carts
            user_note = data.get("user_note")  # Notes to add/update
            cart_id = data.get("cart_id")  
            group_id = data.get("group_id")  

            if not user_id or not user_note or not cart_id:
                return JsonResponse(
                    {"error": "user_id, cart_id, and restaurant_notes are required."}, status=400
                )

            cart_collection = db["Cart"]

            cart = cart_collection.find_one({"_id": cart_id})
            if not cart:
                return JsonResponse({"error": "Cart not found for the given cart_id."}, status=404)

            # group order
            if group_id:
                if cart.get("group_id") != group_id:
                    return JsonResponse({"error": "Cart does not belong to the given group_id."}, status=400)

                # Find the user entry in the group cart
                user_entry = next(
                    (entry for entry in cart.get("group_members", []) if entry.get("added_by") == user_id), None
                )
                if not user_entry:
                    return JsonResponse({"error": "User not found in group cart."}, status=404)
                
                cart_collection.update_one(
                    {"_id": cart_id, "group_members.user_id": user_id},  
                    {"$set": {"group_members.$.user_note": user_note}}  
                )


                return JsonResponse({"message": "Restaurant notes added/updated successfully for group cart."}, status=200)

            # individual cart
            else:
                # Verify the cart belongs to the user
                if cart.get("user_id") != user_id:
                    return JsonResponse({"error": "Cart does not belong to the given user_id."}, status=400)
                
                # Update restaurant notes at the cart level
                cart_collection.update_one(
                    {"_id": cart_id},
                    {"$set": {"user_note": user_note}}
                )

                return JsonResponse({"message": "Restaurant notes added/updated successfully for individual cart."}, status=200)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method. Use PUT."}, status=405)


# Collections
cart_collection = db["Cart"]
user_data_collection = db["UserData"]
restaurant_menu_collection = db["RestaurantMenuData"]

def is_same_day(created_at):
    """Checks if the provided timestamp is from today."""
    try:
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))  # Convert from ISO string to datetime

        if isinstance(created_at, datetime):
            # Get today's date in UTC and compare
            today = datetime.utcnow().date()
            return created_at.date() == today

        return False  # Invalid format
    except Exception as e:
        # print(f"Error in is_same_day: {e}")
        return False

@csrf_exempt
def get_progressbar_data(request):
    if request.method == "POST":
        try:
            # Parse request body
            data = json.loads(request.body)

            cart_id = data.get("cart_id")
            use_default = data.get("use_default", False)
            specific_user_id = data.get("user_id")

            if not cart_id:
                return JsonResponse({"error": "cart_id is required."}, status=400)

            is_group_cart = cart_id.startswith("group_cart_")

            # Fetch cart data
            cart_data = cart_collection.find_one({"_id": cart_id})
            if not cart_data:
                return JsonResponse({"error": f"No cart found for ID {cart_id}."}, status=404)

            restro_id = cart_data.get("restro_id", "N/A")
            restaurant_data = restaurant_menu_collection.find_one({"_id": restro_id})
            if not restaurant_data or "menu" not in restaurant_data:
                return JsonResponse({"error": f"No menu found for restaurant ID {restro_id}."}, status=404)

            menu_dict = {dish["_id"]: dish for dish in restaurant_data.get("menu", [])}

            # Use the fixed `is_same_day()` function
            if not is_same_day(cart_data.get("created_at")):
                return JsonResponse({"message": "The cart was not created today. Skipping energy calculation."}, status=200)

            users_data = []

            if is_group_cart:
                for group_member in cart_data.get("group_members", []):
                    added_by = group_member.get("user_id", "N/A")

                    if specific_user_id and added_by != specific_user_id:
                        continue

                    user_dishes = group_member.get("ordered_dishes", [])
                    user_result = process_user_dishes(added_by, user_dishes, menu_dict, use_default)
                    users_data.append(user_result)

            else:
                user_id = cart_data.get("user_id", "N/A")
                user_dishes = cart_data.get("ordered_dishes", [])
                user_result = process_user_dishes(user_id, user_dishes, menu_dict, use_default)
                users_data.append(user_result)

            return JsonResponse({
                "cart_id": cart_id,
                "restaurant_id": restro_id,
                "users": users_data
            }, status=200)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method. Use POST."}, status=405)


def process_user_dishes(user_id, user_dishes, menu_dict, use_default):
    """Processes the dishes and kcal goals for a user (individual or group)."""
    total_enerc_value = 0
    user_details = user_data_collection.find_one({"_id": user_id})
    
    if not user_details:
        return {"user": user_id, "error": "User data not found."}

    default_goal_kcal = float(user_details.get("goals", {}).get("default_goal", {}).get("kcal", {}).get("value", 0))
    live_goal_kcal = float(user_details.get("goals", {}).get("live_goal", {}).get("kcal", {}).get("value", 0))

    goal_kcal = default_goal_kcal if use_default else live_goal_kcal

    user_dishes_data = []

    for dish in user_dishes:
        dish_id = dish.get("dish_id", "N/A")
        dish_name = dish.get("name", "N/A")
        quantity = dish.get("quantity", 0)

        menu_item = menu_dict.get(dish_id)
        if menu_item and menu_item.get("dish_name") == dish_name:
            nutrients = menu_item.get("dish_variants", {}).get("normal", {}).get("full", {}).get("nutrients", [])
            enerc = next((n for n in nutrients if n["name"] == "ENERC"), None)

            if enerc:
                enerc_value = enerc.get("quantity", 0)
                total_enerc = enerc_value * quantity
                total_enerc_value += total_enerc
                user_dishes_data.append({
                    "dish_id": dish_id,
                    "dish_name": dish_name,
                    "quantity": quantity,
                    "energy_per_dish": enerc_value,
                    "total_energy": total_enerc
                })

    percentage_eaten = (total_enerc_value / goal_kcal * 100) if goal_kcal > 0 else 0
    remaining_goal_kcal = goal_kcal - total_enerc_value

    return {
        "user": user_id,
        "goal_kcal": goal_kcal,
        "total_energy": total_enerc_value,
        "percentage_eaten": percentage_eaten,
        "remaining_kcal": remaining_goal_kcal,
        "dishes": user_dishes_data
    }





