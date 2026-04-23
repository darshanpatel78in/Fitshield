from asyncio.log import logger
import copy
from io import BytesIO
import json
import os
import re
from tkinter import Image
import uuid
from background_task import background
from fitshield_webapp.AI.AIModel.ai_image_model import generate_img
from fitshield_webapp.AI.AIModel.ai_model2 import process_ingredients_nutrients_from_model2
from rest_framework import status
from fitshield_webapp.AI.AIModel.ai_model3 import adjust_quantities_with_min_max
from fitshield_webapp.AI.AIModel.model_helpers.display_nutrients_name import replace_macronutrients_with_display_names
from fitshield_webapp.utils.generate_id import generate_dish_id, generate_ingredient_id
from fitshield_webapp.utils.mail import send_admin_email
from fitshield_webapp.utils.restaurant_claim_pdf import create_restaurant_pdf, fetch_menu_data, fetch_restaurant_data
from fitshield_webapp.utils.user_claim_pdf import create_user_pdf
from ...AI.AIModel.model_helpers.energy_calculation_percentage import calculate_nutrient_energy_distribution
from ...utils.format_validate import normalizarion, sanitize_cooking_method
from ...utils.logging_utils import get_logger
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response
from fitshield_webapp.AI.AIModel.model_helpers.exist_create import is_restaurant_exists, validate_request_data, get_or_create_restaurant, is_dish_exists_in_menu
from ...AI.AIModel.ai_model1 import chat_session, generate_dish_from_model1
from ...AI.AIModel.claim_model import get_the_nutrients_tags
from ...AI.AIModel.model_helpers.manage_dish_data import save_to_model_data, save_to_restaurant_data, save_to_restaurant_model_data
from werkzeug.utils import secure_filename

import logging
from ...utils.format_validate import normalizarion, sanitize_cooking_method, store_notification
import threading
from config.s3_connection import s3_client, bucket_name

# Configure the root logger
logging.basicConfig(
    level=logging.DEBUG,  # Allow all log levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

from datetime import datetime, timedelta, timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from config.connection import db  # Assuming your MongoDB connection is in config/connection.py
from django.utils.timezone import now
import time

@csrf_exempt
def add_last_reminder_to_dishes(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        dish_collection = db["RestaurantMenuData"]
        # current_time = datetime.now(timezone.utc).replace(microsecond=0).isoformat() 
        current_time = now().replace(tzinfo=None).isoformat(timespec='microseconds')

        # Iterate through each restaurant document
        for restaurant in dish_collection.find():
            restro_id = restaurant["_id"]
            menu_items = restaurant.get("menu", [])

            # Iterate through each dish in the menu
            for dish in menu_items:
                dish_id = dish["_id"]

                # Update the dish with 'last_reminder_sent'
                update_result = dish_collection.update_one(
                    {"_id": restro_id, "menu._id": dish_id},
                    {"$set": {"menu.$.created_at": current_time}}
                )

                if update_result.modified_count > 0:
                    print(f"Updated dish {dish_id} in restaurant {restro_id}")
                else:
                    print(f"Dish {dish_id} in restaurant {restro_id} not updated (possibly already has last_reminder_sent)")

        return JsonResponse({"message": "last_reminder_sent added to all dishes successfully"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# Dishes Management

@api_view(['GET'])
def get_dishes(request):
    try:
        restro_id = request.GET.get('restro_id')
        dish_id = request.GET.get('dish_id')
        is_verified = request.GET.get('is_verified')

        # Validate request parameters
        if restro_id == "null" or not restro_id:
            return JsonResponse({"error": "restro_id is required and cannot be null"}, status=400)
        if dish_id == "null":
            dish_id = None
        if is_verified == "null" or is_verified is None:
            return JsonResponse({"error": "is_verified is required and cannot be null"}, status=400)

        if is_verified.lower() not in ['true', 'false']:
            return JsonResponse({"error": "is_verified must be 'true' or 'false'"}, status=400)
        is_verified = is_verified.lower() == 'true'

        # Query the MongoDB collection
        restaurantmenudata_collection = db["RestaurantMenuData"]
        restro_query = {"_id": restro_id}

        restaurant = restaurantmenudata_collection.find_one(restro_query)
        if not restaurant:
            return Response({"error": "Restaurant not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get menu from the restaurant data
        menu = restaurant.get("menu", [])
        if not menu:
            return Response({"message": "No Dishes Available"}, status=status.HTTP_200_OK)

        # Filter the menu based on verification status
        filtered_menu = [dish for dish in menu if dish.get('is_verified', False) == is_verified]

        # Function to arrange ingredients by category
        def arrange_ingredients_by_category(dish):
            categories = dish.get('categories', {})
            category_order = ['essential', 'primary', 'secondary', 'flexible']

            sorted_ingredients = []
            uncategorized_ingredients = []

            for category in category_order:
                for variant in dish.get('dish_variants', {}).get('normal', {}).get('full', {}).get('ingredients', []):
                    if variant.get('name') in categories.get(category, []):
                        sorted_ingredients.append(variant)
                        
            categorized_ingredients = {ingredient.get('name') for ingredient in sorted_ingredients}
            for variant in dish.get('dish_variants', {}).get('normal', {}).get('full', {}).get('ingredients', []):
                if variant.get('name') not in categorized_ingredients:
                    uncategorized_ingredients.append(variant)

            # Combine categorized ingredients first and then uncategorized
            sorted_ingredients.extend(uncategorized_ingredients)

    
            return sorted_ingredients

        # Iterate through all dishes and sort their ingredients
        for dish in filtered_menu:
            if 'dish_variants' in dish and 'normal' in dish['dish_variants']:
                if 'full' in dish['dish_variants']['normal']:
                    dish['dish_variants']['normal']['full']['ingredients'] = arrange_ingredients_by_category(dish)

                if 'half' in dish['dish_variants']['normal']:
                    dish['dish_variants']['normal']['half']['ingredients'] = arrange_ingredients_by_category(dish)

        # Replace macronutrients with display names (if needed)
        filtered_menu = replace_macronutrients_with_display_names(filtered_menu)

        # If dish_id is provided, filter the specific dish
        if dish_id:
            dish = next((d for d in filtered_menu if str(d.get("_id")) == str(dish_id)), None)
            if not dish:
                return Response(
                    {"error": "Dish not found or not verified"},
                    status=status.HTTP_404_NOT_FOUND
                )
            dish = replace_macronutrients_with_display_names(dish)
            return Response({"dish": dish}, status=status.HTTP_200_OK)

        # Return the filtered and sorted menu
        return Response({"menu": filtered_menu}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": "An unexpected error occurred", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
def get_unverified_dishes(request):
    if request.method == "GET":
        try:
            restro_id = request.GET.get('restro_id')

            if not restro_id:
                return JsonResponse({'message': 'Invalid input! Please provide restro_id.'}, status=400)

            restaurantmenudata_collection = db["RestaurantMenuData"]

            restaurant = restaurantmenudata_collection.find_one({"_id": restro_id})
            if not restaurant:
                return JsonResponse({'message': 'Restaurant not found!'}, status=404)

            unverified_dishes = []
            verified_dishes = []
            unverified_category_map = {}
            verified_category_map = {}

            def find_similarity_key(category):
                similarity_key = category.split('/')[0].strip().lower()
                return similarity_key

            for dish in restaurant.get("menu", []):
                dish_id = dish.get("_id")
                if not dish_id:
                    continue
                
                meal_categories = dish.get("meal_category", [])
                
                if not dish.get("is_verified", True):
                    # Take only the first category in the list
                    first_category = meal_categories[0] if meal_categories else None
                    
                    unverified_dishes.append({
                        "dish_id": dish.get("_id"),
                        "dish_name": dish.get("dish_name"),
                        "meal_category": [first_category] if first_category else [],
                        "is_dish_approved": dish.get("is_dish_approved")
                    })
                    # Track unverified dish categories (only first category)
                    if first_category:
                        similarity_key = find_similarity_key(first_category)
                        if similarity_key not in unverified_category_map:
                            unverified_category_map[similarity_key] = {
                                'category': first_category,
                                'dish_count': 0
                            }
                        unverified_category_map[similarity_key]['dish_count'] += 1
                else:
                    # if dish.get("is_out_of_stock", False):
                    #     continue  # Skip this dish if it's out of stock
                    if dish.get("is_dish_approved") is not True:
                        continue
                    
                    verified_dishes.append({
                        "dish_id": dish.get("_id"),
                        "dish_name": dish.get("dish_name"),
                        "meal_category": meal_categories,
                        "is_dish_approved": dish.get("is_dish_approved")
                    })
                    # Track verified dish categories
                    meal_categories = dish.get("meal_category", [])
                    for category in meal_categories:
                        similarity_key = find_similarity_key(category)
                        if similarity_key not in verified_category_map:
                            verified_category_map[similarity_key] = {
                                'category': category,
                                'dish_count': 0
                            }
                        verified_category_map[similarity_key]['dish_count'] += 1

            # Sorting category lists to maintain the correct order
            verified_category_list = sorted([value['category'] for value in verified_category_map.values()])
            unverified_category_list = sorted([value['category'] for value in unverified_category_map.values()])

            # Construct the category count objects in the same order as the categories
            unverified_category_count = {category: unverified_category_map[find_similarity_key(category)]['dish_count'] for category in unverified_category_list}
            verified_category_count = {category: verified_category_map[find_similarity_key(category)]['dish_count'] for category in verified_category_list}

            data = {
                "unverified_dish_count": len(unverified_dishes),
                "unverified_dishes": unverified_dishes,
                "verified_dish_count": len(verified_dishes),
                "verified_dishes": verified_dishes,
                "unverified_categories": unverified_category_list,
                "verified_categories": verified_category_list,
                "unverified_category_count": unverified_category_count,
                "verified_category_count": verified_category_count
            }

            return JsonResponse(data, status=200)

        except Exception as e:
            # print(f"Error: {e}")
            return JsonResponse({'message': 'Internal server error!'}, status=500)
    else:
        return JsonResponse({'message': 'Invalid request method! Only GET is allowed.'}, status=405)

# def complete_dish_processing(dish_id, dish_data):
#     try:
#         processed_results = {}  # This should be replaced with actual processing results
#         # db["RestroData"].update({"_id": dish_id})
#         logging.info(f"Completed processing for dish ID {dish_id}.")
#     except Exception as e:
#         logging.error(f"Error processing dish {dish_id}: {str(e)}")

@api_view(['POST'])
def add_dish(request):
    try:
        logging.info("Processing add_dish request.")
        dish_data = request.data
        restro_id = dish_data.get('restro_id')
        logging.debug(f"Restaurant ID: {restro_id}, Dish data: {dish_data}")
        dish_name = dish_data.get('dish_name')
        if not dish_name:
            logging.warning("Dish name is missing in the request.")
            return JsonResponse(
                {"error": "Dish name is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        if dish_name:
            dish_name = " ".join(dish_name.split()).title()
            normalized_dish_name = normalizarion(dish_name)
        else:
            return Response(
                {"error": "Dish name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        desc = dish_data.get('desc')
        is_desc = str(dish_data.get('is_desc', 'false')).lower() == 'true'
        price = dish_data.get('price')
        is_price = str(dish_data.get('is_price', 'false')).lower() == 'true'

        logging.debug(f"Description: {desc}, Is Desc: {is_desc}")

        missing_fields = validate_request_data(dish_data)
        if missing_fields:
            return Response(
                {"error": f"Missing fields: {', '.join(missing_fields)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if is_restaurant_exists(restro_id):
            logging.warning(f"Restaurant ID '{restro_id}' does not exist.")
            return Response(
                {"error": f"Restaurant ID '{restro_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        restaurant = get_or_create_restaurant(restro_id)
        if not restaurant:
            logging.error(f"Restaurant ID '{restro_id}' does not exist.")
            return Response(
                {"error": f"Restaurant ID '{restro_id}' does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if is_dish_exists_in_menu(restro_id, normalized_dish_name):
            logging.warning(f"The dish {dish_name} already exists in the menu.")
            return Response(
                {"error": f"The dish {dish_name} already exists in menu"},
                status=status.HTTP_409_CONFLICT
            )
            
         # Save initial dish data with is_processing=true
        dish_data['is_processing'] = True 
        dish_data["dish_name"] = dish_name  
        
        # Insert the initial dish data with is_processing=True into the database
        restro_collection = db["RestaurantMenuData"]
        restro_collection.update_one(
            {"_id": restro_id},
            {"$push": {"menu": dish_data}} 
        )
        logging.info(f"Added dish '{dish_data['dish_name']}' to the menu of restaurant '{restro_id}' with processing flag.")

        # Start background processing
        threading.Thread(target=dish_processing, args=(dish_data,dish_data['restro_id'], price, is_price, desc, is_desc)).start()
        
        return Response(dish_data, status=status.HTTP_200_OK)
    
    except Exception as e:
        logging.error(f"Error in add_dish: {str(e)}", exc_info=True)
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
def dish_processing(dish_data,restro_id, price, is_price, desc, is_desc):
        # threading.Thread(target=complete_dish_processing, args=(dish_data['restro_id'], dish_data)).start()
        modeldata_collection = db["ModelData"]
        dish_name = dish_data.get("dish_name")
        
        # logging.info(f"Generating dish data for {dish_name}.")
        ai_data = generate_dish_from_model1(restro_id, dish_name , modeldata_collection, chat_session, price, is_price, desc, is_desc)
        logging.debug("Calculating nutrient energy distribution.")
        percentages = calculate_nutrient_energy_distribution(ai_data)
        ai_data["distributed_percentage"] = percentages
        logging.debug(f"Nutrient distribution: {percentages}")

        # main_food_claims, less_important_claims, lack_of_nutrients_data = get_the_nutrients_tags(ai_data)
        # ai_data["food_claims"] = main_food_claims
        # ai_data["lack_of_nutrients_data"] = lack_of_nutrients_data
        # ai_data["less_important_claims"] = less_important_claims
        # logging.debug(f"Food claims: {main_food_claims}, Lack of nutrients: {lack_of_nutrients_data}")

        main_food_claims, less_important_claims, lack_of_nutrients_data, claims_details = get_the_nutrients_tags(ai_data)
        ai_data["food_claims"] = main_food_claims
        ai_data["lack_of_nutrients_data"] = lack_of_nutrients_data
        ai_data["less_important_claims"] = less_important_claims
        ai_data["claims_details"] = claims_details
        logging.debug(f"Food claims: {main_food_claims}, Lack of nutrients: {lack_of_nutrients_data}")

        cooking_method = ai_data.get("cooking_method", [])
        sanitized_cooking_methods = [sanitize_cooking_method(method) for method in cooking_method]
        ai_data["cooking_method"] = sanitized_cooking_methods
        ai_data["cooking_style"] = sanitized_cooking_methods[0] if sanitized_cooking_methods else None
        logging.debug(f"Cooking style (sanitized): {ai_data['cooking_style']}")


        flexible_items = ai_data['categories']['flexible']
        logging.debug(f"Flexible items: {flexible_items}")

        ai_data = adjust_quantities_with_min_max(ai_data)

        # Iterate through the ingredients and update the is_close flag if the ingredient name matches a flexible item
        for variant_type, variant_data in ai_data['dish_variants'].items():
            for variant_size, details in variant_data.items():
                if 'ingredients' in details:
                    for ingredient in details['ingredients']:
                        if ingredient['name'] in flexible_items:
                            ingredient['is_close'] = True  # Update is_close to True
                            logging.debug(f"Ingredient {ingredient['name']} marked as close.")

        calculate_nutrients_list = ai_data.get("dish_variants", {}).get("normal", {}).get("full", {}).get("nutrients", [])
        ingredient_distributed_nutrients = ai_data.get("dish_variants", {}).get("normal", {}).get("full", {}).get("calculate_nutrients", {})

        restrodata_collection  = db["RestroData"]
        restaurant_name = restrodata_collection.find_one(
            {"_id": restro_id}, {"name": 1, "_id": 0}  
        )

        if not calculate_nutrients_list or not ingredient_distributed_nutrients:
            send_admin_email(
                issue_type="Nutrient Issue",
                restaurant_name=restaurant_name,
                restro_id=restro_id,
                dish_id=dish_id,
                description="Nutrient values could not be generated while adding dish. Please investigate the issue"
            )
    
        restro_collection = db["RestroData"]
        dish_name = ai_data.get("dish_name")
        restaurant = restro_collection.find_one({"_id": restro_id})
        if restaurant:
            restaurant_name = restaurant.get("name")
            dish_id = generate_dish_id(restaurant_name, dish_name)
            logging.info(f"Generated dish ID: {dish_id}")
            if not is_desc:
                logging.info("Saving data to common database.")
                save_to_model_data(ai_data)

            else:
                logging.info("Saving data to specialized database.")
                save_to_restaurant_model_data(restro_id, restaurant, ai_data, dish_id)

            logging.info("Saving data to restaurant menu data.")
            save_to_restaurant_data(restro_id, ai_data,dish_id)
        # complete_dish_processing(restro_id,dish_data)
        
        send_admin_email(
                issue_type="Dish Approve Request",
                restaurant_name=restaurant_name,
                restro_id=restro_id,
                dish_id=dish_id,
                description=f"New Dish Added for Approval - {dish_name}"
            )


        notifications_collection = db["Notification"]
        notification_message = store_notification(
            collection=notifications_collection,
            restro_id=restro_id,
            notification_type="Dish",
            event="Dish Added",
            description=f"Dish '{dish_name}' has been successfully added!",
            details={"dish_name": dish_name, "dish_id": ai_data["_id"]}
        )
        logging.info(f"Dish {dish_name} added successfully!")

def update_serving_size(restro_id, dish_id, ingredient_name, new_quantity):
    try:
        restaurantmenudata_collection = db["RestaurantMenuData"]

        # Fetch dish data
        dish = restaurantmenudata_collection.find_one(
            {"_id": restro_id, "menu._id": dish_id},
            {"menu.$": 1}
        )

        if not dish or "menu" not in dish or not dish["menu"]:
            return {"error": f"Dish with ID '{dish_id}' not found for restaurant ID '{restro_id}'."}, 404

        dish_data = dish["menu"][0]
        # print(dish_data)

        # Find the ingredient to update
        ingredients = dish_data["dish_varients"]["normal"]["full"]["ingredients"]
        ingredient_to_update = next(
            (ingredient for ingredient in ingredients if ingredient["name"].lower() == ingredient_name.lower()), None
        )

        if not ingredient_to_update:
            return {"error": f"Ingredient '{ingredient_name}' not found in the dish data."}, 400

        try:

            original_quantity = float(ingredient_to_update["quantity"])
            new_quantity = float(new_quantity)
        except ValueError:
            return {"error": "Invalid 'new_quantity'. It must be a number."}, 400
        
        # print("quanityyy")
        # print(original_quantity)
        # print(new_quantity)

        if new_quantity <= 0:
            return {"error": "New quantity must be greater than 0."}, 400

        # Calculate scaling factor

        scaling_factor = new_quantity / original_quantity
        ingredient_to_update["quantity"] = new_quantity

        # Update serving size
        # original_serving_size = float(dish_data.get("serving", {}).get("size", 0))
        original_serving_size = float(dish_data.get("dish_varients", {}).get("normal", {}).get("full", {}).get("serving", {}).get("size", 0))

        # print(original_serving_size)

        new_serving_size = round(original_serving_size * scaling_factor, 2)
        # print(dish_data)
        dish_data["dish_varients"]["normal"]["full"]["serving"]["size"] = str(new_serving_size)

        # Update the dish data in the database
        # print(dish_data)
        restaurantmenudata_collection.update_one(
            {"_id": restro_id, "menu._id": dish_id},
            {"$set": {"menu.$": dish_data}}
        )
        # print("doneeeeeeeee insertinggggggggggggg")
        return {"message": "Serving size updated successfully.", "updated_dish": dish_data}, 200

    except Exception as e:
        return {"error": str(e)}, 500

# @csrf_exempt
# def add_jaindish(request):
#     if request.method == "POST":
#         try:
#             request_data = json.loads(request.body)
#             restro_id = request_data.get('restro_id')
#             dish_id = request_data.get('dish_id')

#             if not (restro_id and dish_id):
#                 return JsonResponse({'message': 'Invalid input data!'}, status=400)

#             dishes_collection = db["RestaurantMenuData"]

#             existing_jain_dish = dishes_collection.find_one({
#                 "_id": restro_id,
#                 "menu": {
#                     "$elemMatch": {
#                         "_id": f"{dish_id}_jain", 
#                         "is_jain": True 
#                     }
#                 }
#             })

#         return Response(
#             {"message": f"Dish with ID '{dish_id}' updated successfully for restaurant '{restro_id}'."},
#             status=status.HTTP_200_OK
#         )

#     except Exception as e:
#         return Response(
#             {"error": "An unexpected error occurred", "details": str(e)},
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR,
#         )

# @csrf_exempt
# def add_jaindish(request):
#     if request.method == "POST":
#         try:
#             request_data = json.loads(request.body)
#             restro_id = request_data.get('restro_id')
#             dish_id = request_data.get('dish_id')

#             if not (restro_id and dish_id):
#                 return JsonResponse({'message': 'Invalid input data!'}, status=400)

            # dishes_collection = db["RestaurantMenuData"]

#             existing_jain_dish = dishes_collection.find_one({
#                 "_id": restro_id,
#                 "menu": {
#                     "$elemMatch": {
#                         "_id": f"{dish_id}_jain", 
#                         "is_jain": True 
#                     }
#                 }
#             })

#             if existing_jain_dish:
#                 return JsonResponse({'message': 'Jain dish already exists!'}, status=400)

#             original_dish = dishes_collection.find_one({
#                 "_id": restro_id,
#                 "menu": {
#                     "$elemMatch": {
#                         "_id": dish_id,
#                         "is_jain": False 
#                     }
#                 }
#             })

#             if not original_dish:
#                 return JsonResponse({'message': 'Original dish not found!'}, status=404)

#             dish_data = next((dish for dish in original_dish['menu'] if dish['_id'] == dish_id), None)
#             if not dish_data:
#                 return JsonResponse({'message': 'Dish data not found!'}, status=404)

#             jain_dish = dish_data.copy()
#             jain_dish['_id'] = f"{dish_id}_jain"
#             jain_dish['is_jain'] = True
            
#             jain_dish['ingredients'] = [
#                 ingredient for ingredient in dish_data.get('ingredients', [])
#                 if not re.search(r'\b(onion|onions|garlic|garlics)\b', ingredient['name'], re.IGNORECASE)
#             ]

#             dishes_collection.update_one(
#                 {"_id": restro_id},
#                 {"$push": {"menu": jain_dish}}
#             )

#             return JsonResponse({'message': 'Jain dish added successfully!'}, status=201)

#         except Exception as e:
#             # print(f"Error: {e}")
#             return JsonResponse({'message': 'Internal server error!'}, status=500)
        
swaps = {
    'Oil': ['Oil','Ghee', 'Olive Oil', 'Coconut Oil'],
    'Butter': ['Butter','Ghee', 'Plant-Based Spreads (Margarine, Avocado)', 'Olive Oil'],
    'Whole Milk': ['Whole Milk','Low-Fat Milk', 'Plant-Based Milk (Almond, Soy)', 'Buttermilk'],
    'Refined Sugar': ['Refined Sugar','Honey', 'Jaggery', 'Agave Syrup', 'Maple Syrup'],
    'Maida': ['Maida','Whole Wheat Flour', 'Multigrain Flour', 'Cassava Flour'],
    'White Rice': ['White Rice','Brown Rice', 'Quinoa', 'Millets (Sorghum, Pearl Millet)'],
    'Salt': ['Salt','Himalayan Pink Salt', 'Low-Sodium Salt', 'Sea Salt'],
    'Yogurt': ['Yogurt','Plant-Based Yogurt (Soy, Almond)', 'Coconut Milk Yogurt'],
    'Cream': ['Cream','Coconut Cream', 'Cashew Cream', 'Greek Yogurt'],
    'Cheese': ['Cheese','Plant-Based Cheese', 'Low-Fat Cheese', 'Ricotta'],
    'Meat': ['Meat','Lean Meat', 'Poultry', 'Plant-Based Proteins (Tofu, Seitan)'],
    'Fish': ['Fish','Lean Fish (Tilapia, Cod)', 'Plant-Based Fish Substitutes'],
    'Pasta': ['Pasta','Whole Wheat Pasta', 'Lentil Pasta', 'Zoodles (Vegetable Noodles)'],
    'Potatoes': ['Potatoes','Sweet Potatoes', 'Yams', 'Cauliflower'],
    'Bread': ['Bread','Whole Grain Bread', 'Sourdough', 'Multigrain Bread'],
    'Eggs': ['Eggs','Plant-Based Egg Replacers (Chickpea Flour, Flaxseed)'],
    'White Sugar': ['White Sugar','Coconut Sugar', 'Date Sugar', 'Stevia', 'Monk Fruit Sweetener'],
    'Soy Sauce': ['Soy Sauce','Tamari', 'Coconut Aminos', 'Low-Sodium Soy Sauce'],
    'Mayonnaise': ['Mayonnaise','Greek Yogurt', 'Avocado Spread', 'Hummus'],
    'Ketchup': ['Ketchup','Tomato Paste', 'Low-Sugar Ketchup', 'Fresh Salsa'],
    'Cornstarch': ['Cornstarch','Arrowroot Powder', 'Tapioca Starch', 'Potato Starch'],
    'White Vinegar': ['White Vinegar','Apple Cider Vinegar', 'Rice Vinegar', 'Lemon Juice'],
    'Soy Milk': ['Soy Milk','Almond Milk', 'Oat Milk', 'Rice Milk'],
    'Ground Beef': ['Ground Beef','Ground Turkey', 'Ground Chicken', 'Textured Vegetable Protein (TVP)'],
    'White Flour Tortillas': ['White Flour Tortillas','Whole Wheat Tortillas', 'Corn Tortillas', 'Lettuce Wraps'],
    'Heavy Cream': ['Heavy Cream','Evaporated Milk', 'Coconut Milk', 'Silken Tofu'],
    'Regular Pasta': ['Regular Pasta','Chickpea Pasta', 'Black Bean Pasta', 'Spiralized Vegetables'],
    'White Bread Crumbs': ['White Bread Crumbs','Panko', 'Almond Flour', 'Oats'],
    'Corn Syrup': ['Corn Syrup','Honey', 'Maple Syrup', 'Agave Nectar'],
    'White Potatoes': ['White Potatoes','Cauliflower', 'Parsnips', 'Turnips'],
    'Coconut Milk': ['Coconut Milk','Almond Milk', 'Cashew Cream', 'Soy Cream'],
    'Peanut Butter': ['Peanut Butter','Almond Butter', 'Sunflower Seed Butter', 'Tahini'],
    'Breadcrumb Coating': ['Breadcrumb Coating','Crushed Nuts', 'Seed Mixes', 'Gluten-Free Crumbs'],
    'Eggs': [ 'Eggs','Flaxseed Meal', 'Chia Seeds', 'Aquafaba (Chickpea Water)'],
    'Cows Milk': ['Cows Milk','Almond Milk', 'Oat Milk', 'Coconut Milk'], #improvement as '
    'Wheat Flour': ['Wheat Flour','Rice Flour', 'Almond Flour', 'Buckwheat Flour'],
    'Butter': ['Butter','Margarine', 'Coconut Oil', 'Plant-Based Butter'],
    'Peanuts': ['Peanuts','Sunflower Seeds', 'Pumpkin Seeds', 'Tahini'],
    'Soy Sauce': ['Soy Sauce','Coconut Aminos', 'Worcestershire Sauce', 'Balsamic Vinegar'],
    'Eggs': ['Eggs','Flaxseed Meal', 'Chia Seeds', 'Applesauce'],
    'Cheese': ['Cheese','Nutritional Yeast', 'Vegan Cheese', 'Cashew Cheese'],
    'Tofu': ['Jackfruit', 'Hearts of Palm', 'Tofu'],
    'Tree Nuts': ['Tree Nuts','Sunflower Seeds', 'Pumpkin Seeds', 'Oats'],
    'Shellfish': ['Shellfish','Mushrooms', 'Firm Tofu', 'Artichoke Hearts'],
    'Gluten': ['Gluten','Cornstarch', 'Potato Starch', 'Arrowroot Powder'],
    'Honey': ['Honey','Agave Nectar', 'Maple Syrup', 'Date Syrup'],
    'Yogurt': ['Yogurt','Coconut Yogurt', 'Almond Yogurt', 'Cashew Yogurt'],
    'Mayonnaise': ['Mayonnaise','Avocado', 'Aquafaba Mayo', 'Hummus'],
    'Gelatin': ['Gelatin','Agar-Agar', 'Pectin', 'Carrageenan'],
    'Breadcrumbs': ['Breadcrumbs','Crushed Cornflakes', 'Rice Flour', 'Ground Almonds'],
    'Pasta': ['Pasta','Rice Noodles', 'Zucchini Noodles', 'Lentil Pasta'],
    'Cream': ['Cream','Coconut Cream', 'Cashew Cream', 'Soy Cream'],
    'Chicken': ['Chicken','Tempeh', 'Seitan', 'Jackfruit'],
    'Beef': ['Beef','Black Beans', 'Mushrooms', 'Lentils'],
    'Soy': ['Soy','Pea Protein', 'Chickpeas', 'Lupini Beans']
}


@csrf_exempt
def add_ingredients(request):
    if request.method == "PUT":
        try:
            # Collections
            allergy_ingredients_collection = db["AllergyIngredientData"]
            menu_collection = db["RestaurantMenuData"]

            # Parse request body
            data = json.loads(request.body)

            # Extract required fields
            restro_id = data.get("restro_id", "").strip()
            dish_id = data.get("dish_id", "").strip()
            ingredient_name = data.get("ingredient_name", "").strip().lower() # Normalize to lowercase
             # Capitalize the first letter of the ingredient name, ensure the rest is lowercase
            # ingredient_name = ingredient_name.lower().capitalize()
            ingredient_name_normalized = re.sub(r'\s+', '', ingredient_name)  # Remove all spaces

            ingredient_quantity = str(data.get("ingredient_quantity", ""))  # Ensure the quantity is a string
            ingredient_unit = data.get("ingredient_unit", "")
            ingredient_description = data.get("ingredient_description", "")
            dish_variants = data.get("dish_variants", None)
            dish_type = data.get("dish_type", None)

            # Validate inputs
            if not restro_id or not dish_id or not ingredient_name or not ingredient_quantity or not ingredient_unit:
                return JsonResponse({"error": "restro_id, dish_id, ingredient_name, ingredient_quantity, and ingredient_unit are required."}, status=400)

            # Check if the ingredient exists in the AllergyIngredientData collection
            allergy_ingredient = allergy_ingredients_collection.find_one({
                "allergy_data.allergy_name": {
                    "$regex": f"^{ingredient_name_normalized}",  # Normalize to match spaces and case insensitivity
                    "$options": "i"
                }
            })

            if allergy_ingredient:
                allergy_data = allergy_ingredient["allergy_data"]
                matching_ingredient = next(
                    (item for item in allergy_data if re.sub(r'\s+', '', item["allergy_name"]).lower() == ingredient_name_normalized),
                    None
                )

                if matching_ingredient:
                    ingredient_id = matching_ingredient["allergy_id"]
                    is_swappable = False
                    swap_items = []  # Assuming no swap items for allergens by default
                else:
                    return JsonResponse({"error": f"Ingredient '{ingredient_name}' not found in AllergyIngredientData."}, status=404)
            else:
                # Generate a new ingredient_id if not found
                ingredient_id = generate_ingredient_id(ingredient_name)
                # print(f"Generated new ingredient ID: {ingredient_id}")
                is_swappable = False
                swap_items = []

            # Check if the ingredient exists in the swaps dictionary
            if ingredient_name in swaps:
                is_swappable = True
                swap_items = swaps.get(ingredient_name, [])  # Get the swap items for the ingredient

            # Prepare the ingredient object
            ingredient = {
                "name": ingredient_name,
                "quantity": ingredient_quantity,  # Ensure the quantity is stored as a string
                "unit": ingredient_unit,
                "description": ingredient_description,
                "id": ingredient_id,
                "is_close": False,
                "is_hide": False,
                "is_swappable": is_swappable,
                "min_value": round(float(ingredient_quantity) * 0.9, 2),  # 90% of the quantity
                "max_value": round(float(ingredient_quantity) * 1.1, 2)   # 110% of the quantity
            }

            if is_swappable:
                ingredient["swap_items"] = swap_items

            # Fetch the dish data to check the current variants and sizes
            dish = menu_collection.find_one({
                "_id": restro_id,
                "menu._id": dish_id  # Searching by _id in menu
            })

            if not dish:
                return JsonResponse({"error": "Dish not found or failed to update ingredients."}, status=404)

            # Initialize a variable to track if the ingredient is already present
            ingredient_already_added = False

            for menu_item in dish["menu"]:
                if not "_id" in menu_item:
                    continue
                if menu_item["_id"] == dish_id:
                    for variant_type in ["normal", "jain"]:
                        if variant_type in menu_item["dish_variants"]:
                            for size in ["full", "half"]:
                                if size in menu_item["dish_variants"][variant_type]:
                                    ingredients = menu_item["dish_variants"][variant_type][size].get("ingredients", [])
                                    for i, existing_ingredient in enumerate(ingredients):
                                        if re.sub(r'\s+', '', existing_ingredient["name"]).lower() == ingredient_name_normalized:
                                            ingredients[i] = ingredient
                                            ingredient_already_added = True
                                            break
                                    if ingredient_already_added:
                                        # Update the database with the new ingredient details
                                        menu_collection.update_one(
                                            {"_id": restro_id, "menu._id": dish_id},
                                            {"$set": {f"menu.$.dish_variants.{variant_type}.{size}.ingredients": ingredients}}
                                        )
                                        return JsonResponse({"message": "Ingredient updated successfully."}, status=200)
                                    break
                        if ingredient_already_added:
                            break
                    if ingredient_already_added:
                        break

            if not ingredient_already_added:  
                for variant_type in ["normal", "jain"]:
                    if variant_type in dish["menu"][0]["dish_variants"]:
                        for size in ["full", "half"]:
                            if size in dish["menu"][0]["dish_variants"][variant_type]:
                                # Push the new ingredient into the specified path
                                menu_collection.update_one(
                                    {"_id": restro_id, "menu._id": dish_id},
                                    {"$push": {f"menu.$.dish_variants.{variant_type}.{size}.ingredients": ingredient}}
                                )
                                return JsonResponse({"message": "Ingredient added successfully."}, status=200)

            # If ingredient is not added
            return JsonResponse({"error": "Ingredient not found or failed to add."}, status=404)

        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method. Use PUT."}, status=405)

@csrf_exempt
def get_ingredients(request):
    try:
        if request.method == "GET":
            ingredient_name = request.GET.get('ingredient_name', '').strip().lower()

            if not ingredient_name:
                return JsonResponse({"error": "ingredient_name query parameter is required."}, status=400)

            allergy_ingredients_collection = db["AllergyIngredientData"]

            # Synonym and substring search setup
            normalized_query = re.escape(ingredient_name)  # Prepare query for regex, escaping to avoid issues with special characters

            # Search for matching ingredients using regex for substring matching
            results = []
            search_results = allergy_ingredients_collection.find({
                "allergy_data.allergy_name": {"$regex": normalized_query, "$options": "i"}
            })

            # Collect all matches
            for entry in search_results:
                for ingredient in entry["allergy_data"]:
                    if normalized_query in ingredient['allergy_name'].lower():  # Substring matching condition
                        results.append({
                            "allergy_id": ingredient["allergy_id"],
                            "allergy_name": ingredient["allergy_name"]
                        })

            if results:
                return JsonResponse({"ingredients": results}, status=200)
            else:
                return JsonResponse({"message": "No ingredients found."}, status=404)

        else:
            return JsonResponse({"error": "Invalid request method. Use GET."}, status=405)

    except Exception as e:
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)



@api_view(['POST'])
def generate_pdf(request):
    try:
        data = request.data  

        restro_id = data.get('restaurant_id')
        dish_id = data.get('dish_id')
        is_restaurant = data.get('is_restaurant', False)

        if not restro_id or not dish_id:
            return JsonResponse({"error": "Missing required fields: restaurant_id or selected_dish"}, status=400)

        restro_data = fetch_restaurant_data(restro_id)

        if not restro_data:
            return JsonResponse({"error": "Failed to fetch restaurant data"}, status=500)

        menu_data = fetch_menu_data(restro_id)

        if not menu_data or 'menu' not in menu_data:
            return JsonResponse({"error": "Menu not found in the restaurant data"}, status=404)

        dish = None
        selected_dish = None
        for item in menu_data.get('menu', []):
            if item.get('_id') == dish_id:
                dish = item
                selected_dish = dish.get('dish_name')
                break

        if not dish:
            return JsonResponse({"error": "Dish not found in the menu"}, status=404)

        buffer = BytesIO()

        if is_restaurant:
            create_restaurant_pdf(restro_data, menu_data, selected_dish, buffer)
        else:
            create_user_pdf(restro_data, menu_data, selected_dish, buffer)

        buffer.seek(0)
        if len(buffer.getvalue()) == 0:
            return JsonResponse({"error": "PDF generation failed, buffer is empty."}, status=500)


        response = HttpResponse(buffer, content_type='application/pdf')

        filename = f"{secure_filename(restro_id)}_{secure_filename(dish_id)}_claim_report.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        print(type(response))
        return response

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
