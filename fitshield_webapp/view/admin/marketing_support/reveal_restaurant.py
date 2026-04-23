import json

from django import db
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt  # Disable CSRF for development purposes
def add_restaurant_list(request):
    if request.method == 'POST':
        try:
            # Parse the JSON body
            data = json.loads(request.body)

            # Debugging: Log the received data (remove in production)
            print("Received Data:", data)

            # Validate required fields
            user_id = data.get('user_id')
            name = data.get('name')
            landmark = data.get('landmark')

            # Check for missing fields or invalid values
            if not user_id:
                return JsonResponse({'error': 'Missing or invalid user_id'}, status=400)
            if not name:
                return JsonResponse({'error': 'Missing or invalid name'}, status=400)
            if not landmark:
                return JsonResponse({'error': 'Missing or invalid landmark'}, status=400)

            # Prepare the data to be stored
            restaurant_data = {
                'user_id': user_id,
                'name': name,
                'landmark': landmark
            }
            restaurantcampaigndata_collection = db['RestaurantCampaignData']

            # Insert into MongoDB
            inserted = restaurantcampaigndata_collection.insert_one(restaurant_data)

            # Respond with success message
            return JsonResponse({
                'message': 'Restaurant added successfully',
                'restaurant': {
                    'id': str(inserted.inserted_id),
                    'user_id': user_id,
                    'name': name,
                    'landmark': landmark
                }
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data. Ensure you are sending a valid JSON payload.'}, status=400)
        except Exception as e:
            print("Error:", str(e))
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)