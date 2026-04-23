import json
import os
import re
from django.conf import settings
from rapidfuzz import process


# Load food data from the JSON file
def load_food_data():
    file_path = os.path.join(settings.BASE_DIR,"fitshield_webapp","AI", "AIModel", "data", "Fitshield.for_searchingNutrients.json")
    try:
        with open(file_path, 'r') as file:
            return json.load(file)  
    except Exception as e:
        return str(e)  


# Extract the portion before the parentheses (used for the food names with extra information)
def extract_food_name_before_parenthesis(food_name):
    if '(' in food_name:
        return food_name.split('(')[0].strip()  
    return food_name.strip() 


# Normalize food name by removing parentheses and extra information and converting to lowercase
def normalize_food_name(food_name):
    food_name_without_parentheses = re.sub(r'\s?\(.*?\)', '', food_name)
    
    return food_name_without_parentheses.strip().lower()


# Search for a food item based on an exact name match
def search_food(food_name):
    data = load_food_data()
    if isinstance(data, str): 
        return data

    food_name_normalized = normalize_food_name(food_name)

    for food in data:
        stored_food_name = normalize_food_name(food['Food name'])

        if food_name_normalized == stored_food_name:
            return food

    return None  


# Suggest food names based on partial input and fuzzy matching
def suggest_food(partial_name):
    partial_name_normalized = partial_name.strip().lower()  
    data = load_food_data()
    
    if isinstance(data, str):  
        return data

    food_names = [normalize_food_name(food['Food name']) for food in data]

    matches = process.extract(partial_name_normalized, food_names, limit=None)

    suggestions = []
    for match in matches:
        if match[1] >= 65:  
            suggestions.append(match[0])

    if not suggestions:
        return {"error": "Food name not found in database, please try again with a correct spelling or search a different food."}
    
    # Return dynamic suggestions
    final_suggestions = []
    for suggestion in suggestions:
        suggestion_cap = suggestion.capitalize()
        for food in data:
            food_name = extract_food_name_before_parenthesis(food['Food name']).capitalize()
            if suggestion_cap == food_name:
                final_suggestions.append(food['Food name'])

    return final_suggestions
