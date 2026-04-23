from asyncio.log import logger
from datetime import datetime
import json
import logging
import random
import uuid

import requests
from config.connection import db
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from nltk.tokenize import sent_tokenize,word_tokenize
from nltk.corpus import stopwords

from fitshield_webapp.utils.format_validate import normalize_string

# Stop words for filtering
stop_words = set(stopwords.words("english"))

@csrf_exempt
def add_allergy(request):
    if request.method == 'POST':
        try:
            # Parse the request body
            data = json.loads(request.body)
            allergy_name = data.get("allergy_name", "").strip().lower()
            user_id = data.get("user_id", "").strip()

            # Validate input
            if not allergy_name or not user_id:
                return JsonResponse({"error": "user_id and allergy_name are required."}, status=400)

            # Access the UserData and AllergyData collections
            user_collection = db["UserData"]
            allergy_collection = db["AllergyData"]

            # Find the user by user_id
            user = user_collection.find_one({"_id": user_id})

            if not user:
                return JsonResponse({"error": f"User with ID {user_id} not found."}, status=404)
            
            # Convert timestamps to IST only if user exists
            user["created_at"] = (user.get("created_at"))
            user["updated_at"] = (user.get("updated_at"))

            # Check if the allergy exists in AllergyData
            allergy_data = allergy_collection.find_one(
                {"_id": "Allergy", "allergy_data.allergy_name": {"$regex": f"^{allergy_name}$", "$options": "i"}},
                {"_id": 0, "allergy_data.$": 1}
            )

            if allergy_data:
                # If allergy is found in the database, fetch details (including img_url)
                allergy = allergy_data["allergy_data"][0]
                allergy_type = allergy.get("allergy_type", [])
                allergy_id = allergy["allergy_id"]
                img_url = allergy.get("img_url", None)
            else:
                # If allergy is not found in the database, generate new allergy_id and allergy_type
                random_number = uuid.uuid4()
                allergy_id = f"{allergy_name.replace(' ', '_')}_{random_number}"
                allergy_type = []

                try:
                    # Query Google Custom Search API for allergy details (but without img_url)
                    CX = "c21f4c0d3ee2749db"  # Replace with your actual Search Engine ID
                    API_KEY = "AIzaSyCNkaqnSoyvZPIoER1OHoDGXjRAD3T_F7A"  # Replace with your actual API Key
                    query = f"What is the type of allergy for {allergy_name}and if that ingredients used for the preparation for any vegetarian and non-vegetarian dishes then count it inside that allergy type of vegetarian and non-vegetarian?"
                    api_url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={API_KEY}&cx={CX}"

                    # Make the API request
                    response = requests.get(api_url)
                    if response.status_code != 200:
                        raise Exception(f"Google API Error: {response.status_code}, {response.text}")

                    # Parse the response
                    results = response.json().get("items", [])

                    # Keyword lists for classification
                    vegetarian_keywords = ["vegetarian", "plant-based", "vegan", "herbivore", "microbial rennet"]
                    non_vegetarian_keywords = ["non-vegetarian", "meat", "chicken", "fish", "pork", "beef", "animal rennet"]
                    egg_keywords = ["egg", "egg-based"]
                    dairy_keywords = ["milk", "dairy", "cheese", "butter", "casein", "whey", "lactose"]

                    # Tokenizing and filtering words for analysis
                    for item in results:
                        snippet = item.get("snippet", "").lower()

                        words = word_tokenize(snippet)
                        filtered_words = [word for word in words if word.isalnum() and word not in stop_words]

                        # Assign allergy type based on detected keywords
                        if any(word in filtered_words for word in vegetarian_keywords):
                            allergy_type.append("vegetarian")
                        if any(word in filtered_words for word in non_vegetarian_keywords):
                            allergy_type.append("non-vegetarian")
                        if any(word in filtered_words for word in egg_keywords):
                            allergy_type.append("egg")
                        if any(word in filtered_words for word in dairy_keywords):
                            allergy_type.append("dairy")

                    # Ensure unique types
                    allergy_type = list(set(allergy_type))

                    # Default to "unknown" if still empty
                    if not allergy_type:
                        allergy_type = ["unknown"]

                except Exception as e:
                    # print(f"Error during Google API call: {e}")
                    allergy_type = ["unknown"]
                
                # No img_url is needed in this case when it's not found in the database
                img_url = None

            # Create the allergy object
            new_allergy = {
                "allergy_id": allergy_id,
                "allergy_name": allergy_name.capitalize(),
                "allergy_type": allergy_type
            }
            if img_url:
                new_allergy["img_url"] = img_url  # Add img_url to the response if it's available

            # Update the user's allergies in the UserData collection
            user_collection.update_one(
                {"_id": user_id},  # Match the user by user_id
                {"$addToSet": {"allergies": new_allergy}}  # Add the new allergy to the array (avoid duplicates)
            )

            # Return success response
            return JsonResponse({
                "message": "Allergy added successfully.",
                "user_id": user_id,
                "allergy": new_allergy
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format."}, status=400)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({"error": "Invalid HTTP method. Use POST."}, status=405)
    
    
@csrf_exempt
def get_allergies(request):
    if request.method == "GET":
        try:
            # Access the UserData and AllergyData collections
            user_collection = db["UserData"]
            allergy_collection = db["AllergyData"]

            # Get the user_id from the request
            user_id = request.GET.get("user_id", None)
            if not user_id:
                return JsonResponse({"message": "User ID is required."}, status=400)

            # Fetch the user's data
            user_data = user_collection.find_one({"_id": user_id})
            if not user_data:
                return JsonResponse({"message": "User not found."}, status=404)

            # Extract diet_preference and user-specific allergies
            diet_preference = user_data.get("diet_preference", None)
            user_allergies = user_data.get("allergies", [])

            # if not diet_preference:
            #     return JsonResponse({"message": "Diet preference not found for the user."}, status=404)

            # Fetch the global allergy data
            allergy_document = allergy_collection.find_one({"_id": "Allergy"}, {"_id": 0, "allergy_data": 1})
            if not allergy_document or "allergy_data" not in allergy_document:
                return JsonResponse({"message": "No allergy data found."}, status=404)

            allergy_data = allergy_document["allergy_data"]

            # Filter allergies based on diet_preference
            filtered_allergies = []
            if diet_preference == "Vegetarian":
                filtered_allergies = [allergy for allergy in allergy_data if "vegetarian" in allergy["allergy_type"]]
            elif diet_preference == "Non-Vegetarian":
                filtered_allergies = [allergy for allergy in allergy_data if "non_vegetarian" in allergy["allergy_type"]]
            elif diet_preference == "Egg":
                filtered_allergies = [
                    allergy
                    for allergy in allergy_data
                    if "vegetarian" in allergy["allergy_type"] or "egg" in allergy["allergy_type"]
                ]
            else:  # Include all allergies for other diet preferences
                filtered_allergies = allergy_data

            # Combine global and user-specific allergies
            all_allergies = filtered_allergies + [
                {"allergy_name": allergy, "allergy_type": ["user_specific"]} if isinstance(allergy, str) else allergy
                for allergy in user_allergies
            ]

            # Remove duplicates by allergy_name
            unique_allergies = {allergy["allergy_name"]: allergy for allergy in all_allergies}
            response_allergies = list(unique_allergies.values())

            # Return the combined and filtered allergy data
            return JsonResponse({"allergies": response_allergies}, status=200)

        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)
    
@csrf_exempt
def search_allergy(request):
    if request.method == "GET":
        try:
            # Parse query parameter for search keyword
            keyword = request.GET.get("keyword", "").strip()

            # Validate input
            if not keyword:
                return JsonResponse({"message": "Keyword is required for searching."}, status=400)

            # Access the Allergy collection
            allergy_collection = db["AllergyIngredientData"]

            # Find the document containing the allergy_data array
            document = allergy_collection.find_one({}, {"allergy_data": 1})  # Fetch only allergy_data

            if not document or "allergy_data" not in document:
                return JsonResponse([], safe=False)  # Return an empty list if no data found

            # Search within the allergy_data array
            allergy_data = document["allergy_data"]
            matching_allergies = [
                allergy for allergy in allergy_data
                if allergy["allergy_name"].lower().startswith(keyword.lower())
            ]

            # Return the search results
            return JsonResponse(matching_allergies, safe=False)

        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)

