from datetime import datetime
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from fitshield_webapp.utils.mail import send_admin_email, send_restro_email

DEFAULT_FROM_EMAIL = "s.fitshield@gmail.com"
from_email = "s.fitshield@gmail.com"

@csrf_exempt
def update_query_status(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            restro_id = data.get('restro_id')
            restro_query_id = data.get('restro_query_id')
            query_id = data.get('query_id')
            status = data.get('status')

            if not restro_id or not query_id or not restro_query_id or not status:
                return JsonResponse({'error': 'Missing required fields'}, status=400)

            valid_statuses = ["Pending", "In Progress", "Resolved", "Closed"]
            if status not in valid_statuses:
                return JsonResponse({'error': 'Invalid status'}, status=400)

            query_collection = db["RestaurantQuery"]
            query_entry = query_collection.find_one({'_id': restro_query_id, 'restro_id': restro_id, "queries.query_id":query_id},{"queries.$":1})

            if not query_entry:
                return JsonResponse({'error': 'Query not found'}, status=404)

            query_collection.update_one(
                {'_id': restro_query_id,
                'restro_id': restro_id, 
                'queries.query_id': query_id
                },
                {'$set': {
                    'queries.$[query].status': status,
                    'updated_at': datetime.utcnow().isoformat()
                }},
                array_filters=[{"query.query_id": query_id}]
            )

            # Send email when query is resolved
            if status == "Resolved":
                email = None
                restaurant_name = "N/A"

                matched_query = query_entry.get("queries",[])[0]
                email = matched_query.get("email", None)
                restaurant_name = matched_query.get("restaurant_name", "N/A")
                query_desc = matched_query.get("query", "N/A")

                for query in query_entry.get("queries",[]):
                    if query["query_id"] == query_id:
                        email = query.get("email", None)
                        restaurant_name = query.get("restaurant_name", "N/A")
                        break
                
                if email:
                    send_restro_email(
                        issue_type="Query Resolved",
                        restaurant_name=restaurant_name,
                        restro_id=restro_id,
                        restro_email=email,
                        query=query_desc,
                        from_email = from_email if from_email else DEFAULT_FROM_EMAIL
                    )

            return JsonResponse({'message': 'Query status updated successfully'}, status=200)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON format'}, status=400)

        except Exception as e:
            return JsonResponse({'error': f"Error updating query: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Invalid HTTP method. Only POST is allowed.'}, status=405)
