from asyncio.log import logger
from decimal import Decimal
import json
from ...utils.logging_utils import get_logger
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
import pytz

#------------------------------------POOJA------------------------


@csrf_exempt
def add_discount(request):
    if request.method == "POST":
        try:
            # Fetch and validate required data
            data = json.loads(request.body)
            restro_id = data.get("restro_id")
            dishes = data.get("dishes", [])

            if not restro_id or not dishes:
                return JsonResponse(
                    {"error": "Restaurant ID and dishes are required."},
                    status=400
                )

            # Fetch restaurant data
            restrodata_collection = db["RestaurantMenuData"]
            restaurant = restrodata_collection.find_one({"_id": restro_id})

            if not restaurant:
                return JsonResponse(
                    {"error": "Restaurant not found with the provided ID."},
                    status=404
                )

            menu = restaurant.get("menu", [])
            updated_dishes = []

            # Update discounts and prices in the menu
            for dish_data in dishes:
                if not "dish_id" in dish_data:
                    continue
                dish_id = dish_data.get("dish_id")
                discount_details = dish_data.get("discount_details")

                if not dish_id or not discount_details:
                    continue

                # Find the dish in the menu
                dish = next((d for d in menu if d["_id"] == dish_id), None)
                if not dish:
                    continue

                # Convert discount details: current_price and discount_price to float with .00 precision
                for discount_type in ["full_discount", "half_discount"]:
                    if discount_type in discount_details:
                        discount = discount_details[discount_type]
                        discount["current_price"] = float(Decimal(discount["current_price"]).quantize(Decimal("0.00")))
                        discount["discount_price"] = float(Decimal(discount["discount_price"]).quantize(Decimal("0.00")))
                        discount["discount_percentage"] = str(discount["discount_percentage"])  # Keep as string
                        discount_details[discount_type] = discount

                # Update discount details in the discount object
                dish["discount"] = discount_details

                # Update prices in dish_variants for full and half discounts
                dish_variants = dish.get("dish_variants", {})
                for discount_type in ["full_discount", "half_discount"]:
                    if discount_type in discount_details:
                        current_price = discount_details[discount_type]["current_price"]

                        # Update normal.variant price for full or half if it exists
                        if "normal" in dish_variants and discount_type.split("_")[0] in dish_variants["normal"]:
                            variant = dish_variants["normal"][discount_type.split("_")[0]]
                            if "price" in variant:
                                variant["price"] = float(Decimal(current_price).quantize(Decimal("0.00")))  # Ensure .00 precision

                        # Update jain.variant price for full or half if it exists
                        if "jain" in dish_variants and discount_type.split("_")[0] in dish_variants["jain"]:
                            variant = dish_variants["jain"][discount_type.split("_")[0]]
                            if "price" in variant:
                                variant["price"] = float(Decimal(current_price).quantize(Decimal("0.00")))  # Ensure .00 precision

                # Append updated dish details for response
                updated_dishes.append({
                    "_id": dish["_id"],
                    "dish_name": dish["dish_name"],
                    "discount": dish["discount"],
                    "dish_variants": dish["dish_variants"],
                })

            # Save the updated restaurant data back to the database
            restrodata_collection.update_one(
                {"_id": restro_id},
                {"$set": {"menu": menu}}
            )

            # Prepare response
            return JsonResponse(
                {
                    "message": "Discount applied successfully.",
                    "updated_dishes": updated_dishes,
                },
                status=200
            )

        except json.JSONDecodeError:
            return JsonResponse(
                {"error": "Invalid JSON format in the request body."},
                status=400
            )

        except Exception as e:
            return JsonResponse(
                {"error": "An unexpected error occurred.", "details": str(e)},
                status=500
            )
    return JsonResponse({"error": "Invalid request method."}, status=405)


@csrf_exempt
def get_discount(request):
    if request.method == "GET":
        try:
            # Extract query parameters
            restro_id = request.GET.get("restro_id")
            is_half = request.GET.get("is_half")  # Boolean-like filter
            category = request.GET.get("category")  # Meal category filter

            # Validate restaurant ID
            if not restro_id:
                return JsonResponse(
                    {"error": "Restaurant ID is required."},
                    status=400
                )

            # Handle null category from the frontend
            if category in [None, "null", "Null", "NULL"]:
                category = None

            # Fetch restaurant data from the database
            restrodata_collection = db["RestaurantMenuData"]
            restaurant = restrodata_collection.find_one({"_id": restro_id})

            if not restaurant:
                return JsonResponse(
                    {"error": "Restaurant not found with the provided ID."},
                    status=404
                )

            menu = restaurant.get("menu", [])

            # Filter dishes based on is_half and category
            filtered_menu = []
            for dish in menu:
                 # New condition checks
                if not (dish.get("is_dish_approved", False) and dish.get("is_verified", False) and not dish.get("is_processing", True)):
                    continue  # Skip dishes not meeting new conditions

                if is_half.lower() == "true":
                    if dish.get("is_half_available") != True:
                        continue  
                elif is_half.lower() == "false":
                    pass

                # If `category` is provided, filter based on its value
                if category and category not in dish.get("meal_category", []):
                    continue

                # Retrieve and format discount details
                discount = dish.get("discount", {})
                for discount_type in ["half_discount", "full_discount"]:
                    if discount_type in discount:
                        discount_object = discount[discount_type]
                        # Ensure current_price and discount_price are properly formatted
                        discount_object["current_price"] = float("{:.2f}".format(float(discount_object.get("current_price", 0))))
                        discount_object["discount_price"] = float("{:.2f}".format(float(discount_object.get("discount_price", 0))))
                        discount_object["discount_percentage"] = str(discount_object["discount_percentage"])
                        discount[discount_type] = discount_object

                # Retrieve and format price from dish_variants
                dish_variants = dish.get("dish_variants", {})
                price = {
                    "full_price": float("{:.2f}".format(float(dish_variants.get("normal", {}).get("full", {}).get("price", 0)))),
                    "half_price": float("{:.2f}".format(float(dish_variants.get("normal", {}).get("half", {}).get("price", 0))))
                }

                # Add the dish to the filtered menu
                filtered_menu.append({
                    "dish_id": dish["_id"],
                    "dish_name": dish.get("dish_name"),
                    "meal_category": category if category else dish.get("meal_category", ["Uncategorized"])[0],
                    "price": price,
                    "is_half_available": dish.get("is_half_available", False),
                    "discount": discount
                })

            # Construct the response
            response = {
                "restaurant_id": restro_id,
                "menu": filtered_menu or [],
                "category": category if category else "All"  # Indicate "All" if no category is passed
            }

            return JsonResponse(response, status=200)

        except Exception as e:
            return JsonResponse(
                {"error": "An unexpected error occurred.", "details": str(e)},
                status=500
            )

    return JsonResponse({"error": "Invalid request method."}, status=405)
