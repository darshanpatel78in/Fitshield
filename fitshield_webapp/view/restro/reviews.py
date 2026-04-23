from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import pytz
from fitshield_webapp.utils.qrcode_manager import generate_qr_code
from ...utils.logging_utils import get_logger
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response
from bson import ObjectId

logger = logging.getLogger(__name__)


@csrf_exempt
def get_reviews(request, restro_id):
    logger.info(f"Received a request to fetch reviews for restaurant ID: {restro_id}.")
    
    if request.method == "GET":
        try:
            if not restro_id:
                logger.warning("Validation failed: restro_id is missing.")
                return JsonResponse({"error": "restro_id is required"}, status=400)

            reviews_collection = db["RestaurantReview"]
            reviews_cursor = reviews_collection.find({"restro_id": restro_id})
            reviews = list(reviews_cursor)

            if not reviews:
                logger.info(f"No reviews found for restaurant ID: {restro_id}.")
                return JsonResponse({"message": "No reviews found for this restaurant"}, status=200)

            # Convert ObjectId and datetime fields properly
            for review in reviews:
                # Convert `_id` to string
                review["_id"] = str(review.get("review_id", review["_id"]))

                # Manually convert ObjectId to string
                if isinstance(review["_id"], ObjectId):
                    review["_id"] = str(review["_id"])

                current_utc_time = datetime.utcnow().isoformat()

                review["created_at"] = current_utc_time
                review["updated_at"] = current_utc_time
                
            logger.info("Successfully fetched reviews.")
            return JsonResponse({"reviews": reviews}, status=200, safe=False)

        except Exception as e:
            logger.exception("Error fetching reviews.")
            return JsonResponse({"error": f"Error fetching reviews: {str(e)}"}, status=500)

    logger.warning("Invalid HTTP method used for get_reviews endpoint.")
    return JsonResponse({"error": "Invalid HTTP method, only GET is allowed"}, status=405)
