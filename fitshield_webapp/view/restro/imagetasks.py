from background_task import background
from datetime import datetime, timedelta
from pymongo import MongoClient
import logging

from fitshield_webapp.AI.AIModel.ai_image_model import generate_img  # Import your image generation function
from config.connection import db

logger = logging.getLogger(__name__)

@background(schedule=60)  # Schedule to run every hour
def check_and_update_dish_images():
    now = datetime.utcnow()  # Use UTC to match the format of your created_at
    restaurants = db["RestaurantMenuData"].find()

    for restaurant in restaurants:
        restro_id = restaurant["_id"]
        for dish in restaurant.get("menu", []):
            created_at = dish.get("created_at")
            is_image_updated = dish.get("is_image_updated", False)  # Check if the image is updated

            if created_at:
                # Convert created_at from ISO format to datetime
                created_at_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))  # Handle UTC timezone
                
                if now - created_at_dt > timedelta(hours=24): 
                    if not is_image_updated:  # Only generate a new image if it's not updated
                        dish_name = dish.get("dish_name")
                        logger.info(f"Generating image for dish: {dish_name} in restaurant: {restro_id}")
                        
                        # Generate the image and get the new image URL
                        image_url = generate_img(restro_id, dish_name)

                        # Update MongoDB with the new image URL and set is_image_updated to True
                        db["RestaurantMenuData"].update_one(
                            {"_id": restro_id, "menu.dish_name": dish_name},
                            {
                                "$set": {
                                    "menu.$.dish_img_url": image_url,  # Update image URL
                                    "menu.$.is_image_updated": True  # Update the flag to True
                                }
                            }
                        )
                        logger.info(f"Image generated and uploaded: {image_url}")
                    else:
                        logger.info(f"No update required for dish: {dish['dish_name']} in restaurant: {restro_id}")
@background(schedule=60)
def update_is_menu_prepared():
    now = datetime.utcnow()  # Use UTC to match the format of your created_at
    restaurants = db["RestroData"].find({"is_menu_prepared": False})
    
    for restaurant in restaurants:
        restro_id = restaurant["_id"]
        created_at = restaurant.get("created_at")
        logger.info(f"Updating is_menu_prepared in restaurant: {restro_id}")
        if created_at:
                # Convert created_at from ISO format to datetime
                created_at_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))  # Handle UTC timezone
                
                if now - created_at_dt > timedelta(hours=24):
                    db["RestroData"].update_one(
                        {"_id": restro_id},
                        {"$set": {"is_menu_prepared": True}}
                    )
                    restaurant["is_menu_prepared"] = True
        else:
                        logger.info(f"No update required for restaurant: {restro_id}")