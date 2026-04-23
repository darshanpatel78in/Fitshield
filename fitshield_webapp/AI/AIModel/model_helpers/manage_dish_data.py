from config.connection import db
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timezone
import pytz

import logging

ist_timezone = pytz.timezone("Asia/Kolkata")

# Configure the root logger
logging.basicConfig(
    level=logging.DEBUG,  # Allow all log levels
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def save_to_model_data(ai_data):
    dish_name = ai_data.get("dish_name")

    if not dish_name:
        logger.error("Dish name is missing in the provided data.")
        return Response({"error": "Dish name is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        modeldata_collection = db["ModelData"]

        existing_dish = modeldata_collection.find_one({"dish_name": dish_name})
        if existing_dish:
            return Response({"message": f"Dish '{dish_name}' already exists in the database."}, status=status.HTTP_200_OK)

        model_result = modeldata_collection.insert_one(ai_data)
        return Response({"message": "Dish added successfully to modeldata!"}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Failed to save dish '{dish_name}' to the database: {e}")
        return Response({"error": "Database insertion failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def save_to_restaurant_model_data(restro_id, restaurant, ai_data, dish_id):

    restro_modeldata_collection = db["RestroModelData"]
    dish_name = ai_data.get("dish_name")

    ai_data["_id"] = dish_id

    restro_modeldata_collection.update_one(
        {"_id": restro_id},
        {"$push": {"menu": ai_data}}
    )
    restro_modeldata_collection.update_one(
        {"_id": restro_id},
        {"$unset": {"menu.$[].dish_id": ""}}
    )

    print("special desc is provided so store it in specialized restro model data")
    model_result = restro_modeldata_collection.insert_one(ai_data)
    return Response({"message": "Dish added successfully to resturant modeldata!"}, status=status.HTTP_200_OK)

def save_to_restaurant_data(restro_id, ai_data, dish_id):
    restaurantmenudata_collection = db["RestaurantMenuData"]
    restaurant = restaurantmenudata_collection.find_one({"_id": restro_id})
    dish_name = ai_data.get("dish_name")

    ai_data["_id"] = dish_id

    # Add Created and Updated time
    current_time = datetime.utcnow().isoformat()
    ai_data["created_at"] = current_time
    ai_data["updated_at"] = current_time
    ai_data["last_reminder_sent"] = current_time
    ai_data["is_processing"] = False  

    if restaurant:
        existing_dish = None
        for dish in restaurant['menu']:
            if isinstance(dish, dict):  
                if dish.get('dish_name', '').lower() == dish_name.lower():
                    existing_dish = dish
                    break
            elif isinstance(dish, str): 
                if dish.lower() == dish_name.lower():
                    existing_dish = dish
                    break

        if existing_dish:
            # If the dish exists, update the existing dish in the menu
            logging.info(f"Dish '{dish_name}' exists. Updating the existing data.")
            restaurantmenudata_collection.update_one(
                {"_id": restro_id, "menu.dish_name": dish_name},
                {"$set": {"menu.$": ai_data}}  # Update the existing dish
            )
            logging.info(f"Updated dish '{dish_name}' in the menu of restaurant '{restro_id}'")
        else:
            # If the dish doesn't exist, append the new dish to the menu
            logging.info(f"Dish '{dish_name}' does not exist. Appending the new data.")
            restaurantmenudata_collection.update_one(
                {"_id": restro_id},
                {"$push": {"menu": ai_data}}  
            )
            logging.info(f"Added dish '{dish_name}' to the menu of restaurant '{restro_id}'")

    restaurantmenudata_collection.update_one(
        {"_id": restro_id},
        {"$unset": {"menu.$[].dish_id": ""}}  # Clean up the dish_id field if necessary
    )

    return Response({"message": "Dish added successfully!"}, status=status.HTTP_200_OK)