from datetime import datetime
import json
from fitshield_webapp.utils.logging_utils import get_logger
from config.connection import db
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from fitshield_webapp.utils.generate_id import generate_review_id

@csrf_exempt
def submit_review(request):
    logger.info("Received a request to submit a review.")
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            logger.debug(f"Request data: {data}")
            user_id = data.get("user_id")
            restro_id = data.get("restro_id")
            logger = get_logger(restro_id)
            order_id = data.get("order_id")
            category_ratings = data.get("category_ratings")
            feedback = data.get("feedback")
            created_at = updated_at = datetime.now()

            if not all([user_id, restro_id, order_id, category_ratings]):
                logger.warning("Validation failed: Missing required fields.")
                return JsonResponse({"error": "Missing required fields"}, status=400)

            try:
                category_ratings = {k: float(v) for k, v in category_ratings.items()}
            except ValueError as e:
                logger.warning(f"Conversion error in category_ratings: {e}")
                return JsonResponse({"error": "All category ratings must be numeric values."}, status=400)

            valid_categories = ["Ambiance", "Food Quality", "Service", "Menu"]

            for category, value in category_ratings.items():
                if category not in valid_categories:
                    logger.warning(f"Invalid category: {category}")
                    return JsonResponse({"error": f"Invalid category: {category}"}, status=400)
                if not isinstance(value, (float, int)) or not (1 <= value <= 5):
                    logger.warning(f"Validation failed for category {category}: {value}")
                    return JsonResponse({"error": f"Rating for {category} must be a float between 1 and 5"}, status=400)

            overall_average = sum(category_ratings.values()) / len(category_ratings)

            reviews_collection = db["RestaurantReview"]

            restaurant = reviews_collection.find_one({"restro_id": restro_id})

            if restaurant:
                for review in restaurant.get("reviews", []):
                    if review["user_id"] == user_id and review["order_id"] == order_id:
                        logger.info("Existing review found. Updating feedback.")
                        review["rating_value"].update({
                            "All": round(overall_average, 2),
                            **category_ratings,
                            "feedback": feedback
                        })

                        reviews_collection.update_one(
                            {"restro_id": restro_id, "reviews.user_id": user_id, "reviews.order_id": order_id},
                            {
                                "$set": {
                                    "reviews.$.rating_value": review["rating_value"],
                                    "updated_at": updated_at
                                }
                            }
                        )
                        return JsonResponse({"message": "Review updated successfully"}, status=200)

                logger.info("No matching review found. Adding a new review.")
                user_review_id = generate_review_id(restro_id) + f"_{user_id}"
                new_review = {
                    "user_review_id": user_review_id,
                    "order_id": order_id,
                    "user_id": user_id,
                    "rating_value": {
                        "All": round(overall_average, 2),
                        **category_ratings,
                        "feedback": feedback
                    },
                    "created_at": created_at
                }
                restaurant["reviews"].append(new_review)

                # Recalculate average rating and total reviews
                all_ratings = [review["rating_value"]["All"] for review in restaurant["reviews"]]
                new_average_rating = sum(all_ratings) / len(all_ratings)
                total_reviews = len(restaurant["reviews"])

                reviews_collection.update_one(
                    {"restro_id": restro_id},
                    {
                        "$set": {
                            "reviews": restaurant["reviews"],
                            "average_rating": round(new_average_rating, 2),
                            "total_reviews": total_reviews,
                            "updated_at": updated_at
                        }
                    }
                )
            else:
                logger.info(f"No restaurant found. Creating a new document for {restro_id}.")
                user_review_id = generate_review_id(restro_id) + f"_{user_id}"
                new_document = {
                    "_id": generate_review_id(restro_id),
                    "restro_id": restro_id,
                    "reviews": [{
                        "user_review_id": user_review_id,
                        "order_id": order_id,
                        "user_id": user_id,
                        "rating_value": {
                            "All": round(overall_average, 2),
                            **category_ratings,
                            "feedback": feedback
                        },
                        "created_at": created_at
                    }],
                    "average_rating": round(overall_average, 2),
                    "total_reviews": 1,
                    "created_at": created_at,
                    "updated_at": updated_at
                }
                reviews_collection.insert_one(new_document)

            logger.info("Review submitted successfully.")
            return JsonResponse({"message": "Review submitted successfully"}, status=201)

        except Exception as e:
            logger.exception("Error submitting review.")
            return JsonResponse({"error": f"Error submitting review: {str(e)}"}, status=500)

    logger.warning("Invalid HTTP method used for submit_review endpoint.")
    return JsonResponse({"error": "Invalid HTTP method, only POST is allowed"}, status=405)
    