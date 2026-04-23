from asyncio.log import logger
from datetime import datetime
import json
import logging
from config.connection import db
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

#Favouritess
@csrf_exempt
def add_favourites(request):
    if request.method == 'POST':
        try:
            # Parse the JSON body
            data = json.loads(request.body)

            # Validate required fields
            user_id = data.get('user_id')
            category = data.get('category')
            entry = data.get('entry')

            if not user_id or not category or not entry:
                return JsonResponse({'error': 'Missing user_id, category, or entry'}, status=400)

            favourites_collection = db['Favourites']

            # Check if the user already has a favourites document
            existing_favourites = favourites_collection.find_one({'user_id': user_id})

            if existing_favourites:
                # If the category already exists, append the entry to the category
                if category in existing_favourites['entries']:
                    # Check if the entry already exists to avoid duplicates
                    for existing_entry in existing_favourites['entries'][category]:
                        if existing_entry.get('restro_id') == entry.get('restro_id') or existing_entry.get('name') == entry.get('name'):
                            return JsonResponse({'message': 'Entry already exists in favourites'}, status=200)

                    # Append the new entry with is_favourite set to False
                    existing_favourites['entries'][category].append({
                        **entry,
                        "is_favourite": True,
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    })
                else:
                    # Add the new category if it doesn't exist
                    existing_favourites['entries'][category] = [{
                        **entry,
                        "is_favourite": True,
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }]

                # Update the document
                favourites_collection.update_one(
                    {'user_id': user_id},
                    {'$set': {'entries': existing_favourites['entries'], 'updated_at': datetime.utcnow().isoformat()}}
                )
            else:
                # Generate a custom _id in the desired format
                count = favourites_collection.count_documents({'user_id': user_id})
                auto_number = count + 1
                custom_id = f"favourites_{user_id}_generated{auto_number}"

                # Create a new favourites document
                new_favourites = {
                    '_id': custom_id,
                    'user_id': user_id,
                    'entries': {
                        category: [{
                            **entry,
                            "is_favourite": True,
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat()
                        }]
                    },
                    'created_at': datetime.utcnow().isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                }
                favourites_collection.insert_one(new_favourites)

            return JsonResponse({'message': 'Favourite added successfully'}, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
def get_favourites(request):
    if request.method == 'GET':
        try:
            # Get the user_id from the request
            user_id = request.GET.get('user_id')

            if not user_id:
                return JsonResponse({'error': 'Missing user_id'}, status=400)

            favourites_collection = db['Favourites']

            # Fetch the favourites document for the user
            favourites = favourites_collection.find_one({'user_id': user_id}, {'_id': 0})

            if not favourites:
                return JsonResponse({'message': 'No favourites found for this user', 'favourites': {}}, status=200)

            return JsonResponse({'message': 'Favourites retrieved successfully', 'favourites': favourites}, status=200)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
 
 
def calculate_open_status(working_hours):
    # Get the current day and time
    now = datetime.datetime.now()
    day_of_week = now.strftime("%A")  # e.g., "Monday"

    # Check if the current day is in working_hours
    if day_of_week in working_hours:
        day_schedule = working_hours[day_of_week]
        if day_schedule.get("isClosed", False):  # Check if the restaurant is closed for the day
            return "Closed", None
        
        # Iterate through the time slots for the current day
        for time_slot in day_schedule.get("time_slot", []):
            start_time = datetime.datetime.strptime(time_slot["start"], "%I:%M %p").time()
            end_time = datetime.datetime.strptime(time_slot["end"], "%I:%M %p").time()

            # Check if the current time is within this time slot
            if start_time <= now.time() <= end_time:
                return "Open", time_slot["end"]  # Return "Open" with the closing time

    # Default to "Closed" if no matching time slot is found
    return "Closed", None
   
@csrf_exempt
def get_restaurant(request):
    try:
        # Optional parameters
        search_query = request.GET.get('search', None)
        city = request.GET.get('city', None)
        user_id = request.GET.get('user_id', None)

        # Connect to collections
        restaurant_collection = db['RestroData']
        favourites_collection = db['Favourites']
        reviews_collection = db['RestaurantReview']

        # Fetch all restaurants
        restaurants = list(restaurant_collection.find({}, {
            "_id": 1, "name": 1, "address": 1, "city": 1, "working_hours": 1
        }))
        # print("Fetched Restaurants:", restaurants)

        # Initialize favourites and ratings
        favourite_map = {}
        ratings_map = {}

        # Fetch user's favourite restaurants
        if user_id:
            user_favourites = favourites_collection.find_one({"user_id": user_id})
            # print("Fetched User Favourites:", user_favourites)
            if user_favourites and "entries" in user_favourites:
                favourite_restaurants = user_favourites["entries"].get("restaurants", [])
                for fav in favourite_restaurants:
                    restro_id = fav.get("restro_id")
                    is_favourite = fav.get("is_favourite", False)
                    if restro_id:
                        favourite_map[restro_id] = is_favourite
        # print("Favourite Map:", favourite_map)
        
        # Fetch restaurant ratings
        ratings_data = list(reviews_collection.find({}, {"restro_id": 1, "average_rating": 1}))
        # print("Ratings Data:", ratings_data)
        for rating in ratings_data:
            restro_id = rating["restro_id"]
            ratings_map[restro_id] = rating.get("average_rating", None)
        # print("Ratings Map:", ratings_map)

        # Apply filters if provided
        if search_query:
            restaurants = [
                restro for restro in restaurants
                if search_query.lower() in restro['name'].lower()
            ]
        if city:
            restaurants = [
                restro for restro in restaurants
                if restro.get('city', '').lower() == city.lower()
            ]

        # Prepare the response
        result = []
        for restro in restaurants:
            restro_id = str(restro["_id"])  # Convert ObjectId to string
            working_hours = restro.get('working_hours', {})
            open_status, close_time = calculate_open_status(working_hours)

            # Append restaurant details
            result.append({
                "restro_id": restro_id,
                "name": restro["name"],
                "rating": ratings_map.get(restro_id, None),  # Get average rating
                "open_status": open_status,
                "close_time": close_time,
                "favourite": favourite_map.get(restro_id, False),  # Fetch `is_favourite` status
                "address": restro.get("address", "")
            })

        # Check if restaurants exist
        if not result:
            return JsonResponse({
                "message": "No restaurants found",
                "restaurants": []
            }, status=200)

        # Return success response
        return JsonResponse({
            "message": "Restaurants retrieved successfully",
            "restaurants": result
        }, status=200)

    except Exception as e:
        # Handle unexpected errors
        return JsonResponse({
            "error": str(e)
        }, status=500)


@csrf_exempt
def get_rawfood(request):
    if request.method == "GET":
        try:
            # Parse query parameters for search
            search_query = request.GET.get("search", "").strip().lower()
            
            # Normalize the search query by removing spaces and hyphens
            normalized_search_query = search_query.replace(" ", "").replace("-", "")

            # Access the Nutrients collection
            nutrients_collection = db["Nutrients"]

            # Build query filter (search functionality)
            nutrients_filter = {}
            if normalized_search_query:
                # Use $expr with $regex to normalize both fields for search
                nutrients_filter = {
                    "$expr": {
                        "$regexMatch": {
                            "input": {
                                "$replaceAll": {
                                    "input": {
                                        "$replaceAll": {
                                            "input": {"$toLower": "$Food name"},
                                            "find": "-",
                                            "replacement": ""  # Remove hyphens from the database field
                                        }
                                    },
                                    "find": " ",
                                    "replacement": ""  # Remove spaces from the database field
                                }
                            },
                            "regex": normalized_search_query  # Use normalized search query
                        }
                    }
                }

            # Fetch all items from the Nutrients collection (or filter if search_query is provided)
            raw_food_items = list(nutrients_collection.find(
                nutrients_filter,
                {"_id": 0}  # Exclude the MongoDB Object ID
            ))

            # If no items are found
            if not raw_food_items:
                return JsonResponse({"message": "No raw food items found"}, status=404)

            # Success response with data
            return JsonResponse({"message": "Raw food items fetched successfully", "data": raw_food_items}, status=200)

        except Exception as e:
            logging.error(f"Error occurred while fetching raw food items: {str(e)}", exc_info=True)
            return JsonResponse({"error": "An error occurred while fetching raw food items"}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Use GET."}, status=405)


@csrf_exempt
def get_homemade_food(request):
    if request.method == "GET":
        try:
            # Parse query parameters for search
            search_query = request.GET.get("search", "").strip().lower().replace(" ", "").replace("-", "")

            # Access the ModelData collection
            model_data_collection = db["ModelData"]

            # Build query filter (search functionality)
            model_data_filter = {}
            if search_query:
                # Use $expr with $regex to normalize both fields for search
                model_data_filter = {
                    "$expr": {
                        "$regexMatch": {
                            "input": {
                                "$replaceAll": {
                                    "input": {
                                        "$replaceAll": {
                                            "input": {"$toLower": "$Food name"},
                                            "find": "-",
                                            "replacement": ""  # Remove hyphens from the database field
                                        }
                                    },
                                    "find": " ",
                                    "replacement": ""  # Remove spaces from the database field
                                }
                            },
                            "regex": search_query  # Use normalized search query
                        }
                    }
                }

            # Fetch the dish name and cooking steps from the ModelData collection
            homemade_food_items = list(model_data_collection.find(
                model_data_filter,
                {"_id": 0, "dish_name": 1, "cooking_steps": 1}  # Return only the dish_name and cooking_steps fields
            ))

            # If no items are found
            if not homemade_food_items:
                return JsonResponse({"message": "No homemade food items found"}, status=404)

            # Format response to include dish name and cooking steps
            recipes = [
                {"dish_name": item["dish_name"], "recipe": item["cooking_steps"]}
                for item in homemade_food_items
            ]

            # Success response with data
            return JsonResponse({"message": "Homemade food recipes fetched successfully", "data": recipes}, status=200)

        except Exception as e:
            logging.error(f"Error occurred while fetching homemade food items: {str(e)}", exc_info=True)
            return JsonResponse({"error": "An error occurred while fetching homemade food recipes"}, status=500)

    return JsonResponse({"error": "Invalid HTTP method. Use GET."}, status=405)

