
 
from datetime import datetime, timezone
import json
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from config.connection import db
from django.http import JsonResponse

menu_collection = db["RestaurantMenuData"]
def get_latest_schema():
    """Fetches the latest dish schema by searching across all restaurants based on created_at timestamp."""
    
    # Fetch all restaurants that have a menu
    restaurants = list(menu_collection.find({"menu": {"$exists": True, "$ne": []}}, {"menu": 1, "created_at": 1}))

    latest_dish = None
    latest_created_at = None

    # Loop through all restaurants to find the latest dish
    for restaurant in restaurants:
        for dish in restaurant["menu"]:
            dish_created_at = dish.get("created_at")  # Fetch dish's created_at timestamp
            
            if dish_created_at is None:
                continue 

            if isinstance(dish_created_at, str):  
                try:
                    dish_created_at = datetime.fromisoformat(dish_created_at)
                except ValueError:
                    continue 
            
            # Convert offset-naive timestamps to UTC
            if dish_created_at.tzinfo is None:  
                dish_created_at = dish_created_at.replace(tzinfo=timezone.utc)  

            # Ensure latest_created_at is initialized properly
            if latest_created_at is None or dish_created_at > latest_created_at:
                latest_dish = dish
                latest_created_at = dish_created_at

    if latest_dish:
        latest_dish.pop("_id", None)  
        return latest_dish
    else:
        return {} 

    
@csrf_exempt
def update_menu(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)

    try:
        data = json.loads(request.body)
        dish_id = data.get("dish_id")
        restro_id = data.get("restro_id")

        if not dish_id and not restro_id:
            return JsonResponse({"error": "Provide either dish_id or restro_id"}, status=400)

        # Dynamically fetch the latest schema from the last added dish
        latest_schema = get_latest_schema()
        # print(f"latest schemaaaaaa:{latest_schema}")

        # Query dishes based on provided ID
        query = {"menu._id": dish_id} if dish_id else {"_id": restro_id}
        restaurants = list(menu_collection.find(query))

        if not restaurants:
            return JsonResponse({"error": "No matching restaurant or dish found"}, status=404)

        updated_count = 0

        for restaurant in restaurants:
            updated_menu = []
            for dish in restaurant.get("menu", []):
                if dish_id and dish["_id"] != dish_id:
                    updated_menu.append(dish)  # Skip dishes that don't match the given dish_id
                    continue

                missing_keys = {key: value for key, value in latest_schema.items() if key not in dish}
                if missing_keys:
                    dish.update(missing_keys)
                    updated_count += 1

                updated_menu.append(dish)

            # Update the menu in the database
            menu_collection.update_one({"_id": restaurant["_id"]}, {"$set": {"menu": updated_menu}})

        return JsonResponse({"message": f"Updated {updated_count} dishes successfully"}, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    