
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from config.connection import db

@csrf_exempt
def delete_restaurant(request):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Invalid request method. Use DELETE.'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
        restro_id = data.get('restro_id')
        if not restro_id:
            return JsonResponse({'error': 'restro_id is required.'}, status=400)
        
        # Read optional parameters
        login = data.get('login', False)
        dish_ids = data.get('dish_ids')  # May be None, a string, or a list
                
        restro_data_collection = db['RestroData']
        restro_menu_data_collection = db['RestaurantMenuData']
        
        # If login is true, delete the restaurant document from both collections.
        if login:
            rd_result = restro_data_collection.delete_one({'_id': restro_id})
            rm_result = restro_menu_data_collection.delete_one({'_id': restro_id})
            return JsonResponse({
                'success': True,
                'message': 'Restaurant deleted from both RestroData and RestaurantMenuData collections.',
                'restro_deleted': rd_result.deleted_count,
                'menu_deleted': rm_result.deleted_count
            })
        else:
            # If dish_ids is provided, delete only those dish objects from the restaurant's menu.
            if dish_ids:
                # Ensure dish_ids is a list.
                if isinstance(dish_ids, str):
                    dish_ids = [dish_ids]
                update_result = restro_menu_data_collection.update_one(
                    {'_id': restro_id},
                    {'$pull': {'menu': {'_id': {'$in': dish_ids}}}}
                )
                return JsonResponse({
                    'success': True,
                    'message': f"{update_result.modified_count} dish(es) deleted from the restaurant's menu."
                })
            else:
                # If no dish_ids provided, clear the entire "menu" array for that restaurant.
                update_result = restro_menu_data_collection.update_one(
                    {'_id': restro_id},
                    {'$set': {'menu': []}}
                )
                return JsonResponse({
                    'success': True,
                    'message': "All dishes deleted from the restaurant's menu."
                })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


restaurantmenudata_collection = db["RestaurantMenuData"]

@csrf_exempt
def add_is_updated_image_to_all(request):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Invalid request method. Use PUT.'}, status=405)
    
    try:
        # Update the 'is_updated_image' field to False for every dish in the menu of all restaurants
        result = restaurantmenudata_collection.update_many(
            {},  # Empty filter to select all documents (all restaurants)
            {"$set": {"menu.$[].is_image_updated": False}}  # Add 'is_updated_image' to each dish in all restaurants
        )

        # If the update is successful
        if result.modified_count > 0:
            return JsonResponse({"message": f"Successfully added 'is_updated_image' to dishes in {result.modified_count} restaurants."}, status=200)
        else:
            return JsonResponse({"error": "No dishes updated in any restaurants."}, status=404)

    except Exception as e:
        # Handle any errors that occur
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def delete_is_updated_image_from_all(request):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Invalid request method. Use PUT.'}, status=405)
    
    try:
        # Remove the 'is_updated_image' field from every dish in the menu of all restaurants
        result = restaurantmenudata_collection.update_many(
            {},  # Empty filter to select all documents (all restaurants)
            {"$unset": {"menu.$[].is_jain": ""}}  # Remove 'is_updated_image' from each dish in all restaurants
        )

        # If the update is successful
        if result.modified_count > 0:
            return JsonResponse({"message": f"Successfully deleted 'is_updated_image' from dishes in {result.modified_count} restaurants."}, status=200)
        else:
            return JsonResponse({"error": "No dishes updated in any restaurants."}, status=404)

    except Exception as e:
        # Handle any errors that occur
        return JsonResponse({"error": str(e)}, status=500)
