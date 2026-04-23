from difflib import SequenceMatcher
import logging
from logging.handlers import RotatingFileHandler
import re
from ...utils.logging_utils import get_logger
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response

@csrf_exempt
def universal_search(request):
    query = request.GET.get("query", "").strip().lower()
    restro_id = request.GET.get("restro_id", "").strip()

    # print(f"Query received: {query}")
    # print(f"Restaurant ID received: {restro_id}")

    # Validate required parameters
    if not query or not restro_id:
        return JsonResponse({"error": "Query and restro_id are required."}, status=400)

    # Synonym maps can be expanded as needed
    synonym_map = {
        # e.g., "idli": ["iddly", "idle"], etc.
    }
    timing_synonym_map = {
        # e.g., "breakfast": ["morning meal"], etc.
    }
    cooking_method_synonym_map = {
        # e.g., "saute": ["sautee", "sauté"], etc.
    }

    def is_fuzzy_match(query, target, threshold=0.7):
        similarity = SequenceMatcher(None, query, target).ratio()
        return similarity >= threshold

    # Basic text normalization
    def normalize(text):
        text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip().lower()

    # Remove spaces entirely (for synonyms that might appear merged)
    def normalize_without_spaces(text):
        return normalize(text).replace(" ", "")

    # Pre-compute normalized variants of the query
    normalized_query = normalize(query)
    query_without_spaces = normalize_without_spaces(query)
    query_with_hyphens = normalized_query.replace(" ", "-")

    # Gather potential synonyms
    query_synonyms = synonym_map.get(normalized_query, [normalized_query])
    query_synonyms += synonym_map.get(query_without_spaces, [])
    query_synonyms.append(query_with_hyphens)

    # print(f"Query Synonyms: {query_synonyms}")

    results = []

    try:
        menu_collection = db["RestaurantMenuData"]
        # Fetch only the menu array for the given restaurant
        menu_data = menu_collection.find_one({"_id": restro_id}, {"menu": 1})
        # print(f"Menu Data Found: {bool(menu_data)}")

        if not menu_data or "menu" not in menu_data:
            print("No menu found for restaurant ID:", restro_id)
        else:
            for dish_entry in menu_data["menu"]:
                raw_dish_name = dish_entry.get("dish_name", "")
                normalized_dish_name = normalize(raw_dish_name)
                dish_name_without_spaces = normalize_without_spaces(raw_dish_name)
                dish_name_with_hyphens = normalized_dish_name.replace(" ", "-")

                # print(f"Checking Dish: {raw_dish_name} (Normalized: {normalized_dish_name})")

                # Check all synonyms to see if the dish name starts with any of them (left-to-right match).
                matched = False
                for syn in query_synonyms:
                    syn = syn.strip().lower()
                    # Left-to-right matching: dish_name.startswith(syn)
                    if (
                        normalized_dish_name.startswith(syn) or
                        dish_name_without_spaces.startswith(syn) or
                        dish_name_with_hyphens.startswith(syn)
                    ):
                        matched = True
                        break

                # Additional check for substring matching within the entire dish name
                if not matched:
                    matched = normalized_query in normalized_dish_name

                if matched:
                    # print(f"Dish Match Found: {raw_dish_name}")
                    results.append({
                        "match": raw_dish_name,
                        "category": dish_entry.get("meal_category", [""])[0].lower()
                            if dish_entry.get("meal_category") else None,
                        "is_dish_approved": dish_entry.get("is_dish_approved"),
                        "dish_name": raw_dish_name,
                        "dish_id": dish_entry.get("_id"),
                        "is_verified": dish_entry.get("is_verified"),
                    })

    except Exception as e:
        print(f"Error querying RestaurantMenuData: {e}")

    if not results:
        print("No matches found for query:", query)
    else:
        print("Matches found:", len(results))

    return JsonResponse(results, safe=False, status=200)

