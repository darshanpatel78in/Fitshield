import copy
from datetime import datetime
import json
import os
import pytz
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework import status
from config.connection import db
from fitshield_webapp.AI.AIModel.ai_model2 import process_ingredients_nutrients_from_model2
from fitshield_webapp.utils.format_validate import store_notification
from fitshield_webapp.utils.mail import send_admin_email
from fitshield_webapp.view.restro.save_json import save_json_to_file
import logging
import pytz

logging.basicConfig(
    filename="update_dish.log", 
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def filter_variant_fields(variant):
    logging.info(f"Filtering variant fields: {variant}")
    return {
        "serving": variant.get("serving"),
        "price": variant.get("price"),
        "ingredients": [
            {
                "name": ing.get("name"),
                "quantity": ing.get("quantity"),
                "unit": ing.get("unit"),
                "id": ing.get("id"),
                "description": ing.get("description"),
                "is_swappable": ing.get("is_swappable", False),
                "swap_items": ing.get("swap_items", []),
                "min_value": ing.get("min_value"),
                "max_value": ing.get("max_value")
            }
            for ing in variant.get("ingredients", [])
        ],
        "nutrients": variant.get("nutrients", []),
        "calculate_nutrients": variant.get("calculate_nutrients", {})
    }

def update_serving_size_as_per_ingredients_quantity(ingredients_tobe_udpated):
    updated_serving_size= 0
    try:
        for ingredient in ingredients_tobe_udpated:
            ingredient_quantity = float(ingredient.get("quantity",0))
            # print(f"ingredient_quantity: {ingredient_quantity}")
            updated_serving_size += ingredient_quantity
    except ValueError:
        logging.warning(f"Invalid quantity value for ingredient: {ingredient}")
    logging.info(f"updated serving size as per ingredients quantity is: {updated_serving_size}")
    return updated_serving_size

def process_ingredients(ingredients, factor=1, exclude_items=None, is_jain_variant=False):
    if exclude_items is None:
        exclude_items = []

    processed_ingredients = []
    for ingredient in ingredients:
        
        ingredient_name_lower = ingredient["name"].lower()

        if is_jain_variant:
            if "garlic" in ingredient_name_lower or "onion" in ingredient_name_lower:
                continue
        
        if any(exclude_item in ingredient_name_lower for exclude_item in exclude_items):
            continue
        
        # if ingredient["name"].lower() in exclude_items:
        #     continue

        # Divide quantity if factor is provided
        processed_ingredient = ingredient.copy()
        processed_ingredient["quantity"] = str(float(ingredient["quantity"]) / factor)

        processed_ingredients.append(processed_ingredient)

    return processed_ingredients

def generate_half_variant(full_replica_dish, updated_fields):
    logging.info("Generating half variant for dish.")

    full_variant = full_replica_dish["dish_variants"]["normal"].get("full", {})
    half_variant = copy.deepcopy(filter_variant_fields(full_variant))
    logging.info("Creating a deep copy of the full variant for the half variant with filteration")

    half_variant["ingredients"] = process_ingredients(full_variant.get("ingredients", []), factor=2)
    logging.info(f"Processed half variant ingredients: {half_variant['ingredients']}")

    serving_data = updated_fields.get("serving", {}).get("half", {})
    if serving_data:
        half_variant["serving"] = {
            "size": str(serving_data.get("size", 1)),  # Use the size from the request, default to 1 if not provided
            "unit": serving_data.get("unit", "g")  # Use the unit from the request, default to 'g' if not provided
        }
        logging.info(f"Updated serving data for half variant: {half_variant['serving']}")

    price_data = updated_fields.get("price", {}).get("half", None)
    if price_data:
        half_variant["price"] = price_data 
        logging.info(f"Updated price for half variant: {half_variant['price']}")

    half_variant["nutrients"] = []
    half_variant["calculate_nutrients"] = {}
    
    full_replica_dish["dish_variants"]["normal"]["half"] = half_variant
    logging.info("Calculating nutrients for half variant.")

    calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(full_replica_dish, "normal", "half")
    logging.info(f"Calculated nutrients: {calculate_nutrients_list}")
    logging.info(f"Distributed ingredient nutrients: {ingredient_distributed_nutrients}")
    
    half_variant["nutrients"] = calculate_nutrients_list
    half_variant["calculate_nutrients"] = ingredient_distributed_nutrients

    full_replica_dish["dish_variants"]["normal"]["half"] = half_variant
    logging.info(f"Final half variant generated: {half_variant}")

    return half_variant

def generate_jain_variant(full_replica_dish, restro_id, dish_id, is_half_available_db, is_jain_available_request):
    logging.info("Generating Jain variant for dish.")

    restrodata_collection = db["RestroData"]
    restaurant_name = restrodata_collection.find_one(
            {"_id": restro_id}, {"name": 1, "_id": 0}  
        )
    if restaurant_name:
        restaurant_name = restaurant_name.get("name", "Unknown Restaurant")  # Handle missing names
    else:
        restaurant_name = "Unknown Restaurant"
    
    full_variant = full_replica_dish["dish_variants"]["normal"].get("full", {})
    jain_variant = {"full": filter_variant_fields(full_variant)}
    jain_replica_dish = copy.deepcopy(full_replica_dish)

    logging.info("Processing Jain ingredients by excluding garlic and onion.")
    jain_variant["full"]["ingredients"] = process_ingredients(
        full_variant["ingredients"],
        exclude_items=["garlic", "onion"],
        is_jain_variant=True
    )

    logging.info("Initializing Jain variant structure if not already present.")
    if "jain" not in jain_replica_dish["dish_variants"]:
        jain_replica_dish["dish_variants"]["jain"] = {}  
        logging.info("Created 'jain' key inside dish_variants.")
    if "half" not in jain_replica_dish["dish_variants"]["jain"]:
        jain_replica_dish["dish_variants"]["jain"]["full"] = {}
        logging.info("Initialized 'full' key inside jain variant.")

    logging.info("Updating Jain full variant with filtered data.")
    jain_replica_dish["dish_variants"]["jain"]["full"].update(jain_variant["full"])

    if "jain" in jain_replica_dish["dish_variants"]:
        jain_replica_dish["dish_variants"]["jain"].update(jain_variant)
        logging.info("Updated Jain variant inside jain_replica_dish.")
    else:
        jain_replica_dish["dish_variants"]["jain"] = jain_variant
        logging.info("Assigned new Jain variant inside jain_replica_dish.")

    logging.info("Processing Jain full variant ingredients by excluding garlic and onion.")
    jain_variant["full"]["ingredients"] = process_ingredients(
        full_variant["ingredients"],
        exclude_items=["garlic", "onion"],
        is_jain_variant=True
    )
    logging.info(f"Jain full variant ingredients processed: {jain_variant['full']['ingredients']}")
    
    logging.info("Calculating nutrients and distributed nutrients for Jain full variant.")
    calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(jain_replica_dish, "jain","full")
    logging.info(f"Calculated nutrients: {calculate_nutrients_list}")
    logging.info(f"Distributed ingredient nutrients: {ingredient_distributed_nutrients}")
    
    logging.info("Updating nutrients and distributed nutrients for Jain full variant.")
    jain_variant["full"]["nutrients"] = calculate_nutrients_list
    jain_variant["full"]["calculate_nutrients"] = ingredient_distributed_nutrients
    
    # 🚨 **SEND EMAIL ALERT IF NUTRIENTS ARE EMPTY**
    if not calculate_nutrients_list or not ingredient_distributed_nutrients:
        logging.error(f"🚨 Nutrient calculation failed for Dish ID {dish_id}, Restaurant ID {restro_id}")
        send_admin_email(
            issue_type="Nutrient Issue",
            restaurant_name=restaurant_name,
            restro_id=restro_id,
            dish_id=dish_id,
            description="Nutrient values could not be generated while updating the Jain full variant of this dish. Please investigate the issue"
        )

    if is_half_available_db or is_jain_available_request:
        logging.info("Processing Jain half variant.")

        half_variant = full_replica_dish["dish_variants"]["normal"].get("half", {})
        logging.info(f"Fetched normal half variant: {half_variant}")

        jain_half_variant = filter_variant_fields(half_variant)
        logging.info(f"Filtered Jain half variant fields: {jain_half_variant}")

        logging.info("Processing ingredients for Jain half variant (excluding garlic and onion).")
        jain_half_variant["ingredients"] = process_ingredients(
            full_variant["ingredients"],
            factor=2,
            exclude_items=["garlic", "onion"]
        )
        logging.info(f"Processed Jain half variant ingredients: {jain_half_variant['ingredients']}")

        jain_replica_dish["dish_variants"]["jain"]["half"] = jain_half_variant
        logging.info("Jain half variant added to Jain replica dish.")

        logging.info("Calculating nutrients for Jain half variant.")
        calculate_nutrients_list_half, calculate_nutrients_data_half = process_ingredients_nutrients_from_model2(jain_replica_dish, "jain", "half")
        logging.info(f"Calculated nutrients for Jain half: {calculate_nutrients_list_half}")
        logging.info(f"Distributed ingredient nutrients for Jain half: {calculate_nutrients_data_half}")

        if not calculate_nutrients_list or not ingredient_distributed_nutrients:
            logging.error(f"🚨 Nutrient calculation failed for Dish ID {dish_id}, Restaurant ID {restro_id}")
            send_admin_email(
                issue_type="Nutrient Issue",
                restaurant_name=restaurant_name,
                restro_id=restro_id,
                dish_id=dish_id,
                description="Nutrient values could not be generated while updating the Jain Half variant of this dish. Please investigate the issue"
            )
        
        jain_half_variant["nutrients"] = calculate_nutrients_list_half
        jain_half_variant["calculate_nutrients"] = calculate_nutrients_data_half
        logging.info("Updated Jain half variant nutrients and calculation data.")

        jain_variant["half"] = jain_half_variant
        logging.info(f"Final Jain half variant stored: {jain_variant['half']}")

    logging.info(f"Final Jain variant generated: {jain_variant}")
    return jain_variant


# if serving size get changed -> ingredients get changed accordingly

def apply_serving_size_and_price_updates(variant, updated_fields, old_serving_size, variant_type):
    if not variant:
        return
    logging.info(f"Applying serving size and price updates for {variant_type}.")
    logging.info(f"Old serving size: {old_serving_size}")

    # **Update Serving Size**
    serving_data = updated_fields.get("serving", {}).get(variant_type, {})
    new_size_val = serving_data.get("size")
    new_unit_val = serving_data.get("unit", "g")  # Default to grams if unit is not provided

    if new_size_val:
        try:
            new_size_val = float(new_size_val)
        except (ValueError, TypeError):
            logging.warning(f"Invalid serving size: {new_size_val}")
            return  # Skip if invalid size

        current_size = float(old_serving_size.get("size", 1) or 1)
        ratio = new_size_val / current_size if current_size > 0 else 1
        logging.info(f"Old serving size: {current_size}, New serving size: {new_size_val}, Ratio: {ratio}")

        # Update serving size
        variant["serving"] = {"size": str(new_size_val), "unit": new_unit_val}

        # Scale ingredient quantities
        for ing in variant.get("ingredients", []):
            try:
                old_qty = float(ing.get("quantity", 0))
                ing["quantity"] = str(old_qty * ratio)
            except ValueError:
                pass

    # **Update Price (full/half)** based on the request
    price_data = updated_fields.get("price", {})
    if variant_type in price_data:
        variant["price"] = price_data[variant_type]
        logging.info(f"Updated price for {variant_type}: {variant['price']}")

    logging.info(f"Completed serving size and pricing updates for {variant_type}.")

def update_ingredients(full_variant, restro_id, dish_id, updated_fields):

    restrodata_collection = db["RestroData"]
    restaurant_name = restrodata_collection.find_one(
            {"_id": restro_id}, {"name": 1, "_id": 0}  
        )
    if restaurant_name:
        restaurant_name = restaurant_name.get("name", "Unknown Restaurant")  # Handle missing names
    else:
        restaurant_name = "Unknown Restaurant"

    if "ingredients" not in updated_fields.get("full", {}):
        logging.info("No ingredient updates found.")
        return full_variant  # No ingredients to update

    logging.info("Updating ingredients for full variant.")
    current_ingredients = full_variant.get("ingredients", [])

    for updated_ingredient in updated_fields["full"].get("ingredients", []):
        ing_id = updated_ingredient.get("id")
        if not ing_id:
            logging.warning(f"Skipping ingredient update: Missing 'id' field in {updated_ingredient}")
            continue

        ingredient_found = False
        for ingredient in current_ingredients:
            if ingredient.get("id") == ing_id:
                ingredient_found = True

                # Handle swapped ingredients
                if updated_ingredient.get("is_swappable", False) and "swap_items" in updated_ingredient:
                    new_name = updated_ingredient["name"]
                    original_name = ingredient["name"]

                    # Ensure the new name is one of the allowed swap items
                    if new_name in updated_ingredient["swap_items"]:
                        logging.info(f"Swapping ingredient '{original_name}' with '{new_name}'.")
                        
                        # Swap ingredient name
                        ingredient["name"] = new_name
                        
                        # Add the original name to swap_items if it's not there
                        if original_name not in ingredient["swap_items"]:
                            ingredient["swap_items"].append(original_name)
                            
                        logging.info(f"Updated ingredient after swapping: {ingredient}")
                    else:
                        logging.warning(f"⚠️ Invalid swap attempt: '{new_name}' is not in {updated_ingredient['swap_items']}. Skipping update.")

                # Update other fields
                for key, value in updated_ingredient.items():
                    if key != "id":
                        ingredient[key] = value
                break

        if not ingredient_found:
            logging.info(f"Adding new ingredient: {updated_ingredient}")
            current_ingredients.append(updated_ingredient)

    full_variant["ingredients"] = current_ingredients
    logging.info(f"Updated ingredients: {current_ingredients}")

    logging.info("Recalculating nutrients for full variant.")
    calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(
        {"dish_variants": {"normal": {"full": full_variant}}}, "normal", "full"
    )
    
    if calculate_nutrients_list and ingredient_distributed_nutrients:
        full_variant["nutrients"] = calculate_nutrients_list
        full_variant["calculate_nutrients"] = ingredient_distributed_nutrients
    else:
        logging.warning("Warning: Nutrient calculation returned empty results!")

    # save_json_to_file(full_variant["nutrients"], "dishes_output", "ing_udpate_calculate_nutrients_list.json" )
    # save_json_to_file(full_variant["calculate_nutrients"], "dishes_output", "ing_udpate_ingredient_distributed_nutrients.json" )

    if not full_variant["nutrients"] or not full_variant["calculate_nutrients"]:
        logging.error(f"Nutrient calculation failed for Dish ID {dish_id}, Restaurant ID {restro_id}")
        send_admin_email(
            issue_type="Nutrient Issue",
            restaurant_name=restaurant_name,
            restro_id=restro_id,
            dish_id=dish_id,
            description="Nutrient values could not be generated while updating the ingredients of full variant dish. Please investigate the issue"
        )

    if "half" in full_variant:
        logging.info("Updating nutrients for half variant.")
        half_variant = full_variant["half"]

        if "ingredients" not in half_variant or not isinstance(half_variant["ingredients"], list):
            half_variant["ingredients"] = []

        half_variant["ingredients"] = process_ingredients(full_variant["ingredients"], factor=2)

        logging.info("Recalculating nutrients for half variant.")
        calculate_nutrients_list_half, ingredient_distributed_nutrients_half = process_ingredients_nutrients_from_model2(
            {"dish_variants": {"normal": {"half": half_variant}}}, "normal", "half"
        )

        if calculate_nutrients_list_half and ingredient_distributed_nutrients_half:
            half_variant["nutrients"] = calculate_nutrients_list_half
            half_variant["calculate_nutrients"] = ingredient_distributed_nutrients_half
            full_variant["half"] = half_variant

    logging.info(f"Final full variant after updating ingredients & swaps: {full_variant}")
    return full_variant



def get_full_replica_dish(restro_id, dish_id):
    try:
        logging.info(f"Fetching full replica dish for restro_id: {restro_id}, dish_id: {dish_id}")

        restaurantmenudata_collection = db["RestaurantMenuData"]

        # Fetch the dish data based on restro_id and dish_id
        dish_data = restaurantmenudata_collection.find_one(
            {"_id": restro_id, "menu._id": dish_id},
            {"menu.$": 1}  # Fetch only the specific dish from the menu array
        )

        # Check if dish data exists
        if not dish_data or "menu" not in dish_data:
            logging.warning(f"Dish not found for restro_id: {restro_id}, dish_id: {dish_id}")
            return Response({"error": "Dish not found."}, status=status.HTTP_404_NOT_FOUND)

        # Extract the dish data
        full_replica_dish = dish_data["menu"][0]
        logging.info(f"Successfully fetched dish data: {full_replica_dish}")

        return full_replica_dish

    except Exception as e:
        logging.error(f"An error occurred while fetching data for restro_id: {restro_id}, dish_id: {dish_id} - Error: {str(e)}")
        return {"error": f"An error occurred while fetching data: {str(e)}"}
     



@api_view(['PUT'])
def update_dish(request):
    try:
        logging.info("Received request to update dish.")
        dish_data = request.data
        restro_id = dish_data.get('restro_id')
        dish_id = dish_data.get('dish_id')
        updated_fields = dish_data.get('updated_fields', {})

        if not restro_id or not dish_id or not updated_fields:
            logging.warning("Missing required fields: restro_id, dish_id, or updated_fields.")
            return Response({"error": "restro_id, dish_id, and updated_fields are required."}, status=status.HTTP_400_BAD_REQUEST)

        logging.info(f"Fetching dish data for restro_id: {restro_id}, dish_id: {dish_id}")
        restaurantmenudata_collection = db["RestaurantMenuData"]
        restrodata_collection = db["RestroData"]

        dish = restaurantmenudata_collection.find_one(
            {"_id": restro_id, "menu": {"$elemMatch": {"_id": dish_id}}},
            {"menu.$": 1}
        )

        restrodata_collection = db["RestroData"]
        restaurant_name = restrodata_collection.find_one(
            {"_id": restro_id}, {"name": 1, "_id": 0}  
        )

        if restaurant_name:
            restaurant_name = restaurant_name.get("name", "Unknown Restaurant")  # Handle missing names
        else:
            restaurant_name = "Unknown Restaurant"
        
        if not dish or "menu" not in dish:
            logging.error(f"Dish with ID '{dish_id}' not found.")
            return Response({"error": f"Dish with ID '{dish_id}' not found."}, status=status.HTTP_404_NOT_FOUND)

        logging.info("Extracting target dish data.")
        target_dish = dish["menu"][0]
        full_replica_dish = copy.deepcopy(target_dish)
        logging.info("Created a deep copy of the target dish for modification.")

        # Access normal_variant and full_variant
        normal_variant = full_replica_dish.setdefault("dish_variants", {}).setdefault("normal", {})
        full_variant = normal_variant.setdefault("full", {})
        logging.info("Initialized normal and full variant structures.")

        # Update the full variant
        if "full" in updated_fields:
            logging.info("Updating full variant ingredients.")
            
            if "ingredients" in updated_fields["full"] and isinstance(updated_fields["full"]["ingredients"], list) and updated_fields["full"]["ingredients"]:
                ingredients_tobe_udpated = updated_fields["full"]["ingredients"]

                #check here each ingredients quantity - total count -> set it to serving size
                confirm_quantity = update_serving_size_as_per_ingredients_quantity(ingredients_tobe_udpated)
                logging.info("Using ingredients from request data.")

            else:
                ingredients_tobe_udpated = full_variant.get("ingredients", [])
            
            full_variant["ingredients"] = ingredients_tobe_udpated
            logging.info(f"Updated full variant ingredients: {ingredients_tobe_udpated}")

            full_replica_dish = get_full_replica_dish(restro_id, dish_id)
            if not full_replica_dish:
                logging.error("Dish not found in database.")
                return Response({"error": "Dish not found."}, status=status.HTTP_404_NOT_FOUND)
            
            logging.info("Successfully fetched full replica dish from database.")
            full_replica_dish["dish_variants"]["normal"]["full"]["ingredients"] = ingredients_tobe_udpated
            full_replica_dish["dish_variants"]["normal"]["full"]["serving"]["size"] = confirm_quantity
            full_replica_dish["dish_variants"]["normal"]["full"]["serving"]["unit"] = "g"

            logging.info("Filtering unnecessary fields before processing nutrients.")
            filtered_dish = {
                key: value
                for key, value in full_replica_dish.items()
                if key not in ["ingredients", "nutrients", "calculate_nutrients"]
            }

            nutrients = filtered_dish.pop("nutrients", [])
            calculate_nutrients = filtered_dish.pop("calculate_nutrients", {})

            filtered_dish["dish_variants"]["normal"]["full"]["nutrients"] = nutrients
            filtered_dish["dish_variants"]["normal"]["full"]["calculate_nutrients"] = calculate_nutrients
            logging.info("Updated nutrients and calculation fields in filtered dish.")

            # save_json_to_file(filtered_dish, "dishes_output", "filtered_dish.json" )

            logging.info("Recalculating nutrients for full variant.")
            calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(filtered_dish, "normal", "full")

            if not calculate_nutrients_list or not ingredient_distributed_nutrients:
                logging.error(f" Nutrient calculation failed for Dish ID {dish_id}, Restaurant ID {restro_id}")
                send_admin_email(
                    issue_type="Nutrient Issue",
                    restaurant_name=restaurant_name,
                    restro_id=restro_id,
                    dish_id=dish_id,
                    description="Nutrient values could not be generated while updating the full variant of this dish. Please investigate the issue"
                )

            logging.info(f"Calculated nutrients for full variant: {calculate_nutrients_list}")
            logging.info(f"Distributed ingredient nutrients for full variant: {ingredient_distributed_nutrients}")

            # full_variant = update_ingredients(filtered_dish, updated_fields)   # uncomment this
            full_variant = update_ingredients(full_replica_dish["dish_variants"]["normal"]["full"], restro_id, dish_id, updated_fields)
            full_replica_dish["dish_variants"]["normal"]["full"]["ingredients"] = full_variant["ingredients"]
            logging.info(f"Updated full_variant ingredients in full_replica_dish: {full_replica_dish['dish_variants']['normal']['full']['ingredients']}")

            filtered_full_data = filter_variant_fields(updated_fields["full"])

        full_replica_dish["dish_variants"]["normal"]["full"].setdefault("serving", {"size": "0", "unit": "g"})
        # full_replica_dish["dish_variants"]["normal"].setdefault("half", {}).setdefault("serving", {"size": "0", "unit": "g"})

        if updated_fields.get("serving"):
            logging.info("Updating serving size and price.")
            serving_data = updated_fields["serving"]

            if "full" in serving_data:
                old_serving_size = full_replica_dish["dish_variants"]["normal"]["full"].get("serving", {"size": "0", "unit": "g"})
                full_replica_dish["dish_variants"]["normal"]["full"]["serving"] = serving_data["full"]
                logging.info(f"Updated full serving size: {serving_data['full']}")
                apply_serving_size_and_price_updates(full_replica_dish["dish_variants"]["normal"]["full"], updated_fields, old_serving_size, "full")
                
                calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(full_replica_dish, "normal", "full")
                logging.info(f"Calculated nutrients normal full: {calculate_nutrients_list}")
                logging.info(f"Distributed ingredient nutrients normal full: {ingredient_distributed_nutrients}")
                full_replica_dish["dish_variants"]["normal"]["full"]["nutrients"] = calculate_nutrients_list
                full_replica_dish["dish_variants"]["normal"]["full"]["calculate_nutrients"] = ingredient_distributed_nutrients
                
                restaurant_name = restrodata_collection.find_one(
                        {"_id": restro_id}, {"name": 1, "_id": 0} 
                    )
                if restaurant_name:
                    restaurant_name = restaurant_name.get("name", "Unknown Restaurant")  # Handle missing names
                else:
                    restaurant_name = "Unknown Restaurant"

                # 🚨 **SEND EMAIL ALERT IF NUTRIENTS ARE EMPTY**
                if not calculate_nutrients_list or not ingredient_distributed_nutrients:
                    logging.error(f"🚨 Nutrient calculation failed for Dish ID {dish_id}, Restaurant ID {restro_id}")
                    send_admin_email(
                        issue_type="Nutrient Issue",
                        restaurant_name=restaurant_name,
                        restro_id=restro_id,
                        dish_id=dish_id,
                        description="Nutrient values could not be generated while updating serving in full variant of this dish. Please investigate the issue"
                    )

            if "half" in serving_data:
                half_variant = full_replica_dish["dish_variants"]["normal"].setdefault("half", {})
                old_serving_size = half_variant.get("serving", {"size": "0", "unit": "g"})
                half_variant["serving"] = serving_data["half"]
                logging.info(f"Updated half serving size: {serving_data['half']}")
                apply_serving_size_and_price_updates(half_variant, updated_fields, old_serving_size, "half")

                calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(full_replica_dish, "normal", "half")
                logging.info(f"Calculated nutrients normal half: {calculate_nutrients_list}")
                logging.info(f"Distributed ingredient normal half: {ingredient_distributed_nutrients}")

                # 🚨 **SEND EMAIL ALERT IF NUTRIENTS ARE EMPTY**
                if not calculate_nutrients_list or not ingredient_distributed_nutrients:
                    logging.error(f"🚨 Nutrient calculation failed for Dish ID {dish_id}, Restaurant ID {restro_id}")
                    send_admin_email(
                        issue_type="Nutrient Issue",
                        restaurant_name=restaurant_name,
                        restro_id=restro_id,
                        dish_id=dish_id,
                        description="Nutrient values could not be generated while updating serving in Half variant of this dish. Please investigate the issue"
                    )


        if "price" in updated_fields:
            logging.info("Updating full dish price after fetching fresh data")
            if "full" in updated_fields["price"]:
                full_replica_dish["dish_variants"]["normal"]["full"]["price"] = updated_fields["price"]["full"]
                logging.info(f"Updated full price: {updated_fields['price']['full']}")
            if "half" in updated_fields["price"]:
                full_replica_dish["dish_variants"]["normal"].setdefault("half", {})["price"] = updated_fields["price"]["half"]
                logging.info(f"Updated half price: {updated_fields['price']['half']}")

        if "is_verified" in updated_fields:
            if 'filtered_full_data' in locals():  # Check if filtered_full_data exists
                filtered_full_data["is_verified"] = updated_fields["is_verified"]
                logging.info(f"Updated verification status: {updated_fields['is_verified']}")

        # Update the Half variant
        if updated_fields.get("is_half_available"):
            logging.info("Generating half variant.")
            half_variant = normal_variant.get("half", {})
            half_variant["ingredients"] = full_variant.get("ingredients", [])
            half_variant = generate_half_variant(full_replica_dish, updated_fields)

            if half_variant:  
                normal_variant["half"] = half_variant
                logging.info("Half variant generated successfully.")
            else:
                logging.warning("Half variant generation failed.")
        # else:
        #     normal_variant.pop("half", None)
        #     logging.info("Half variant removed.")

        #  Update the jain variant
        if updated_fields.get("is_jain_available", False):
            logging.info("Generating Jain variant.")
            jain_variant = generate_jain_variant(full_replica_dish, restro_id, dish_id, updated_fields.get("is_half_available", False), True)
            full_replica_dish["dish_variants"]["jain"] = jain_variant
            logging.info("Jain variant generated successfully.")
        # else:
        #     full_replica_dish["dish_variants"].pop("jain", None)
        #     logging.info("Jain variant removed.")

        logging.info("Preparing update queries for MongoDB.")

        variant_update_query = {f"menu.$.{k}": v for k, v in full_replica_dish.items()}
        logging.info(f"Variant update query: {variant_update_query}")

        field_update_query = {
            "menu.$.dish_description": updated_fields.get("dish_description", target_dish.get("dish_description")),
            "menu.$.cooking_steps": updated_fields.get("cooking_steps", target_dish.get("cooking_steps")),
            "menu.$.cooking_style": updated_fields.get("cooking_style", target_dish.get("cooking_style")),
            "menu.$.is_out_of_stock": updated_fields.get("is_out_of_stock", target_dish.get("is_out_of_stock")),
            "menu.$.meal_category": updated_fields.get("meal_category", target_dish.get("meal_category")),
            "menu.$.special": updated_fields.get("special", target_dish.get("special")),
            "menu.$.is_half_available": updated_fields.get("is_half_available", target_dish.get("is_half_available")),
            "menu.$.is_jain_available": updated_fields.get("is_jain_available", target_dish.get("is_jain_available")),
            "menu.$.is_verified": updated_fields.get("is_verified", target_dish.get("is_verified")),
        }
        logging.info(f"Field update query: {field_update_query}")
        
        # Ensure `updated_at` is updated in IST
        #updated_time_ist =datetime.now(ist_timezone).isoformat()
        update_query = {**variant_update_query, **field_update_query  ,
        "menu.$.updated_at": datetime.utcnow().isoformat(),
        # "menu.$.created_at": original_created_at  # ✅ Ensure created_at remains unchanged

        }

        # update_query["menu.$.created_at"] = original_created_at 

        logging.info(f"Final update query: {update_query}")

        try:
            logging.info("Executing update in MongoDB.")
            restaurantmenudata_collection.update_one(
                {"_id": restro_id, "menu._id": dish_id},
                {"$set": update_query}
            )

            store_notification(
                collection=db["Notification"],
                restro_id=restro_id,
                notification_type="Dish",
                event="Dish Updated",
                description=f"Dish '{target_dish['dish_name']}' has been successfully updated!",
                details={"dish_name": target_dish["dish_name"], "dish_id": dish_id}
            )

            logging.info("Dish update successful.")
            return Response({"message": "Dish updated successfully."}, status=status.HTTP_200_OK)
        
        except Exception as e:
            logging.error(f"Error updating dish: {str(e)}")
            return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({"error": f"An unexpected error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

