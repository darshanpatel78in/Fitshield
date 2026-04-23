from config.connection import db
import logging
# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log format to include time, log level, and message
    handlers=[
        logging.StreamHandler()  
    ]
)
logger = logging.getLogger(__name__)

def validate_request_data(dish_data):
    required_fields = ["restro_id", "dish_name"]
    missing_fields = [field for field in required_fields if not dish_data.get(field)]
    return missing_fields

#create new res if not exist
def get_or_create_restaurant(restro_id):
    restaurantmenudata_collection = db["RestaurantMenuData"]
    restaurant = restaurantmenudata_collection.find_one({"_id": restro_id})
    
    if not restaurant:
        logger.info(f"Restaurant with ID {restro_id} not found. Creating a new entry.")
        new_restaurant = {"_id": restro_id, "menu": []}
        restaurantmenudata_collection.insert_one(new_restaurant)
        restaurant = new_restaurant  # Use the newly created restaurant

    return restaurant

def is_restaurant_exists(restro_id):
    restrodata_collection = db["RestroData"]
    restrodata = restrodata_collection.find_one({"_id": restro_id})
    
    if not restrodata:
        logger.info(f"Restaurant with ID {restro_id} not found. Creating a new entry.")
        return True

    return False

def is_dish_exists_in_menu(restro_id, normalized_dish_name):
    restaurantmenudata_collection = db["RestaurantMenuData"]
    restaurant = restaurantmenudata_collection.find_one({"_id": restro_id})
    if not restaurant or "menu" not in restaurant:
        return False

    for dish in restaurant["menu"]:
        stored_dish_name = dish.get("dish_name", "")
        stored_normalized_name = stored_dish_name.replace(" ", "").lower()
        if stored_normalized_name == normalized_dish_name:
            return True

    return False



