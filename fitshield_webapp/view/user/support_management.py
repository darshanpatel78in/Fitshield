from asyncio.log import logger
from datetime import datetime
import json
from config.connection import db
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
def user_support(request):
    logger.info("Received a request for the support API.")

    if request.method == 'POST':
        try:
            tutorials_collection = db["UserSupport"]

            # Parse JSON body
            try:
                data = json.loads(request.body)
                tutorial = data.get("tutorial")
                blogs = data.get("blogs")
                faqs = data.get("faqs")
                terms_and_conditions = data.get("terms_and_conditions")
                privacy_policy = data.get("privacy_policy")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON format: {e}")
                return JsonResponse({"error": "Invalid JSON format."}, status=400)

            # Validate required fields
            required_keys = ["tutorial", "blogs", "faqs", "terms_and_conditions", "privacy_policy"]
            for key in required_keys:
                if key not in data:
                    logger.error(f"Missing required field: {key}")
                    return JsonResponse({"error": f"Missing required field: {key}"}, status=400)

            support_id = "user"
            support_data = {
                "_id": support_id,
                "tutorial": tutorial,
                "blogs": blogs,
                "faqs": faqs,
                "terms_and_conditions": terms_and_conditions,
                "privacy_policy": privacy_policy,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

            # Insert data into the collection
            insert_result = tutorials_collection.insert_one(support_data)

            return JsonResponse({"message": "Data inserted successfully.", "id": str(insert_result.inserted_id)}, status=201)

        except Exception as e:
            logger.exception("Critical error while handling POST request for support API.")
            return JsonResponse({"error": str(e)}, status=500)


    logger.warning("Invalid HTTP method used for support API.")
    return JsonResponse({"error": "Invalid method. Use GET or POST."}, status=400)
