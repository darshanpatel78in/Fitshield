from rest_framework.decorators import api_view
from django.http import JsonResponse
from config.connection import db
from rest_framework.response import Response
from rest_framework import status
import google.generativeai as genai
from fitshield import settings
from home_cooking.ai_model1 import chat_session, generate_dish_from_model1
from bson.json_util import dumps
from thefuzz import process
from typing import Dict, Any, Optional

# Configure Gemini AI
genai.configure(api_key=settings.GENERATIVEAI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

def scale_ingredients(ingredients: list, persons: int) -> list:
    """Scale ingredient quantities based on number of persons."""
    if persons <= 1:
        return ingredients
    
    scaling_factor = (200 * persons) / 200
    for ingredient in ingredients:
        ingredient["quantity"] = str(round(float(ingredient["quantity"]) * scaling_factor, 2))
    return ingredients

def find_dish_in_db(dish_name: str, persons: int) -> Optional[Dict]:
    """Search for dish in database and scale ingredients if found."""
    UserDishesData_collection = db["UserDishesData"]
    dish_names = [dish["dish_name"] for dish in UserDishesData_collection.find({}, {"dish_name": 1})]
    best_match, score = process.extractOne(dish_name, dish_names)
    
    if score > 80:
        dish_data = UserDishesData_collection.find_one(
            {"dish_name": best_match}, 
            projection={"_id": 0}
        )
        if dish_data and persons > 1:
            ingredients = dish_data["dish_variants"]["normal"]["full"]["ingredients"]
            dish_data["dish_variants"]["normal"]["full"]["ingredients"] = scale_ingredients(ingredients, persons)
        return dish_data
    return None

def generate_dish_from_ai(dish_name: str, persons: int) -> Optional[Dict]:
    """Generate dish data using AI model."""
    valid_dish = find_by_model(dish_name)
    if valid_dish == "False":
        return None
        
    dish_data = generate_dish_from_model1(valid_dish, chat_session, 1)
    UserDishesData_collection = db["UserDishesData"]
    UserDishesData_collection.insert_one(dish_data)

    if persons > 1:
        ingredients = dish_data["dish_variants"]["normal"]["full"]["ingredients"]
        dish_data["dish_variants"]["normal"]["full"]["ingredients"] = scale_ingredients(ingredients, persons)
    
    return dish_data

def find_by_model(input_text: str) -> str:
    """Query Gemini AI model for dish name validation."""
    prompt = f"""
    Given the input word or phrase, if it resembles a valid dish name (food item), 
    respond with the accurate dish name (correcting any misspellings or variations). 
    If it does not resemble any valid dish name (food item), respond with "False". 
    Do not explain or generate additional text.

    Input: {input_text}
    """
    
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=10,
            temperature=0.1
        )
    )
    return response.text.strip()

@api_view(['POST'])
def get_dish(request) -> Response:
    """Main endpoint to retrieve dish information."""
    try:
        dish_name = request.data.get('dish_name')
        persons = int(request.data.get('persons') or 1)

        if not dish_name:
            return JsonResponse(
                {"error": "dish_name is required and cannot be null"}, 
                status=400
            )

        # Try finding dish in database first
        dish_data = find_dish_in_db(dish_name, persons)
        
        # If not found, generate using AI
        if not dish_data:
            dish_data = generate_dish_from_ai(dish_name, persons)
            if not dish_data:
                return Response(
                    {"error": "Dish not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )

        return Response(dumps(dish_data), status=status.HTTP_200_OK)
    

    except Exception as e:
        return Response(
            {
                "error": "An unexpected error occurred", 
                "details": str(e)
            }, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )