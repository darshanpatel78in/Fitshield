import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
from venv import logger

import pytz
from fitshield_webapp.utils.qrcode_manager import generate_qr_code
from ...utils.logging_utils import get_logger
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response
from bson import ObjectId

# Define IST timezone
ist_timezone = pytz.timezone("Asia/Kolkata")

@csrf_exempt
def support(request):
    # logger.info("Received a request to fetch support data.")
    if request.method == 'GET':
        try:
            tutorials_collection = db["RestaurantSupport"]

            response_data = {
                "tutorials": [],
                "blogs": [],
                "faqs": [],
                "terms_and_conditions": [],
                "privacy_policy": []
                }

            # Fetch Tutorials
            try:
                tutorials_cursor = tutorials_collection.find({}, {"_id": 0, "tutorial": 1})
                tutorials_list = list(tutorials_cursor)
                formatted_tutorials = []
                for tutorial_entry in tutorials_list:
                    if not isinstance(tutorial_entry, dict):
                        # print(f"Skipping invalid entry: {tutorial_entry}")
                        continue

                    tutorial = tutorial_entry.get("tutorial", {})
                    tutorial_data = {
                        "tutorial_id": tutorial.get("tutorial_id"),
                        "title": tutorial.get("title"),
                        "videos": []
                    }
                    # Add video details if available
                    video_list = tutorial.get("videos", [])
                    if not isinstance(video_list, list):
                        # print(f"Invalid videos data format: {video_list}")
                        continue
                    if video_list:
                        for video in video_list:
                            if not isinstance(video, dict):
                                # print(f"Skipping invalid video entry: {video}")
                                continue
                            #if exist then get it from aws if not
                            # thumbnail_url = generate_thumbnail_for_video(video)
                            tutorial_list = tutorial_data["videos"]
                            tutorial_list.append({
                                "video_id": video.get("video_id"),
                                "title": video.get("title"),
                                "video_url": video.get("video_url"),
                                "thumbnail_url": video.get("thumbnail_url"),
                                "duration": video.get("duration"),
                                "description": video.get("description")
                            })
                    formatted_tutorials.append(tutorial_data)
                response_data["tutorials"] = formatted_tutorials
            except Exception as e:
                logger.error(f"Error fetching tutorials: {e}")

            # Fetch Blogs
            try:
                blogs_cursor = tutorials_collection.find({}, {"_id": 0, "blogs": 1})
                blog_list = []
                for doc in blogs_cursor:
                    if 'blogs' in doc:
                        for blog in doc['blogs']:
                            blog_list.append({
                                "video_url": blog.get("video_url"),
                                "thumbnail_url": blog.get("thumbnail_url"),
                                "title": blog.get("title"),
                                "description": blog.get("description"),
                                "user_url": blog.get("user_url"),
                                "username": blog.get("username"),
                                "video_id": blog.get("video_id"),
                                "category": blog.get("category"),
                                "created_at": blog.get("created_at"),
                                "updated_at": blog.get("updated_at"),

                            })
                response_data["blogs"] = blog_list
            except Exception as e:
                logger.error(f"Error fetching blogs: {e}")

            # Fetch FAQs
            try:
                faqs_cursor = tutorials_collection.find({}, {"_id": 0, "faqs": 1})
                faq_list = []
                for doc in faqs_cursor:
                    if 'faqs' in doc:
                        for faq in doc['faqs']:
                            faq_list.append({
                                "question": faq.get("question"),
                                "answer": faq.get("answer")
                            })
                response_data["faqs"] = faq_list
            except Exception as e:
                logger.error(f"Error fetching FAQs: {e}")

            # Fetch Terms and Conditions
            try:
                terms_data = tutorials_collection.find_one({}, {"_id": 0, "terms_and_conditions": 1})
                response_data["terms_and_conditions"] = terms_data.get("terms_and_conditions") if terms_data else []
                if not response_data["terms_and_conditions"]:
                    logger.warning("Terms and conditions data is missing.")
            except Exception as e:
                logger.error(f"Error fetching terms and conditions: {e}")

            # Fetch Privacy Policy
            try:
                privacy_data = tutorials_collection.find_one({}, {"_id": 0, "privacy_policy": 1})
                response_data["privacy_policy"] = privacy_data.get("privacy_policy") if privacy_data else []
                if not response_data["privacy_policy"]:
                    logger.warning("Privacy policy data is missing.")
            except Exception as e:
                logger.error(f"Error fetching privacy policy: {e}")

            try:
                menu_prepared_cursor = tutorials_collection.find({}, {"_id": 0, "menu_prepared": 1})
                menu_list = []
                for doc in menu_prepared_cursor:
                    if 'menu_prepared' in doc:
                        # print(f"Document: {doc}")  # Log the raw document
                        for menu in doc['menu_prepared']:
                            # print(f"Menu Object: {menu}")  # Log the raw menu object
                            video_url = menu.get("video_url", "Missing video_url")
                            # print(f"Video URL: {video_url}")  # Log the retrieved video_url

                            menu_list.append({
                                "screen_id": menu.get("screen_id", "N/A"),
                                "video_url": video_url,  # Add fallback for debugging
                                "thumbnail_url": menu.get("thumbnail_url", "N/A"),
                            })
                response_data["menu_prepared"] = menu_list
            except Exception as e:
                logger.error(f"Error fetching menu prepared: {e}")


            # Final Validation Check: Ensure at least one section has data
            if not any(response_data.values()):
                # logger.warning("No data available in the support API response.")
                return JsonResponse({"error": "No data found."}, status=404)

            # logger.info("Successfully fetched support data.")
            return JsonResponse(response_data, safe=False, status=200)

        except Exception as e:
            # logger.exception("Critical error in support API.")
            return JsonResponse({"error": str(e)}, status=500)

    # logger.warning("Invalid HTTP method used for support API.")
    return JsonResponse({"error": "Invalid method. Use GET."}, status=400)