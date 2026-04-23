import json
import re
from django.http import JsonResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import google.generativeai as genai
import pymongo
import urllib.parse
from langchain_community.retrievers import PineconeHybridSearchRetriever
from pinecone import Pinecone
from langchain_huggingface import HuggingFaceEmbeddings
from pinecone_text.sparse import BM25Encoder
import warnings
import logging
from pathlib import Path

from fitshield_webapp.AI.AIModel.model_helpers.validate_format import normalize_spaces
from .model_helpers.initialize_nutrients_unit import total_nutrients
from config.connection import db
from nltk.stem import PorterStemmer
# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log format to include time, log level, and message
    handlers=[
        logging.StreamHandler()  
    ]
)
logger = logging.getLogger(__name__)

nutrients_collection = db["Nutrients"]

# Get the current working directory (you can also use environment variables)
api_key = "c2468019-302c-411e-bf36-c802d54d7a87"
unit_index_name = "hybrid-search-langchain-unitconversion"
ingredient_index_name = "hybrid-search-langchain-pincone"

base_dir = Path(__file__).resolve().parent  # E:\Fitshield\ftishield\fitshield_webapp\AI\AIModel

ingredients_bm25_path = base_dir / "data" / "ingredients_bm25_values.json"
unit_bm25_path = base_dir / "data" / "unit_bm25_values.json"

# print(f"Ingredients Path: {ingredients_bm25_path}")
# print(f"Unit Path: {unit_bm25_path}")

ingredient_bm25_encoder = BM25Encoder().load(str(ingredients_bm25_path))
unit_bm25_encoder = BM25Encoder().load(str(unit_bm25_path))
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
pc = Pinecone(api_key=api_key)
unit_index = pc.Index(unit_index_name)
ingredient_index = pc.Index(ingredient_index_name)
unit_retriever = PineconeHybridSearchRetriever(
    embeddings=embeddings, sparse_encoder=unit_bm25_encoder, index=unit_index
)
ingredient_retriever = PineconeHybridSearchRetriever(
    embeddings=embeddings, sparse_encoder=ingredient_bm25_encoder, index=ingredient_index
)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

genai.configure(api_key="AIzaSyC7PuTD0r_KKmKwqcnqpZTeA0-84bOSj24")
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

def extract_ingredients(dish_name, description, ingredients):

    # Initialize the stemmer
    stemmer = PorterStemmer()

    # Normalize and clean the dish name and description
    normalized_dish_name = dish_name.lower().replace('-', ' ')
    normalized_description = description.lower().replace('-', ' ')

    # Extract words from the dish name
    words_in_name = re.findall(r'\b\w+\b', normalized_dish_name)

    # Extract words from the part after "with" in the description, if present
    after_with = re.findall(r'\b\w+\b', description.split("with", 1)[0].strip().lower()) if "with" in description else description.split()

    # Combine words from dish name and the part after "with"
    combined_words = set(words_in_name + after_with)

    # Stem all words in the combined text
    stemmed_text = {stemmer.stem(word) for word in combined_words}

    # Match ingredients using stemmed words
    matched_ingredients = [
    ingredient['name'] for ingredient in ingredients
    if any(
        re.search(rf'\b{re.escape(word)}\b', stemmer.stem(ingredient['name'].lower()))
        for word in stemmed_text
    )]

    return matched_ingredients

def is_indian_id(id_value):

    id_value = str(id_value)
    # Check if the ID meets all conditions
    return (
        len(id_value) == 4 and             # Condition 1: Length is 4
        id_value[0].isupper() and          # Condition 2: Starts with a capital letter
        id_value[1:].isalnum()             # Condition 3: Remaining characters are numeric
    )


def nutrient_distribution_collection(total_nutrients):
    return{
          "Macro nutrients - Energy": total_nutrients.get("ENERC", 0),
          "Macro nutrients - Carbs": total_nutrients.get("CHOAVLDF", 0),
          "Macro nutrients - Proteins": total_nutrients.get("PROTCNT", 0),
          "Macro nutrients - Fats": total_nutrients.get("FATCE", 0),
          "Macro nutrients - Fibers": total_nutrients.get("FIBTG", 0),
          "Water soluble Vitamin - Primary": (
              total_nutrients.get("THIA", 0) + total_nutrients.get("RIBF", 0) + total_nutrients.get("NIA", 0) +
              total_nutrients.get("PANTAC", 0) + total_nutrients.get("VITB6C", 0) + total_nutrients.get("VITC", 0)
          ),
          "Water soluble Vitamin - Secondary": (
              total_nutrients.get("BIOT", 0) + total_nutrients.get("FOLSUM", 0)
          ),
          "Fat soluble Vitamin - Primary": (
              total_nutrients.get("RETOL", 0) + total_nutrients.get("ERGCAL", 0) + total_nutrients.get("CHOCAL", 0) +
              total_nutrients.get("VITK1", 0) + total_nutrients.get("VITK2", 0) + total_nutrients.get("CARTOID", 0)
          ),
          "Fat soluble Vitamin - Secondary": total_nutrients.get("VITE", 0),
          "Minerals - Primary": (
              total_nutrients.get("AL", 0) + total_nutrients.get("CD", 0) + total_nutrients.get("CA", 0) + total_nutrients.get("CR", 0) +
              total_nutrients.get("CO", 0) + total_nutrients.get("CU", 0) + total_nutrients.get("FE", 0) + total_nutrients.get("PB", 0) +
              total_nutrients.get("LI", 0) + total_nutrients.get("MG", 0) + total_nutrients.get("MN", 0) + total_nutrients.get("MO", 0) +
              total_nutrients.get("NI", 0) + total_nutrients.get("P", 0) + total_nutrients.get("K", 0) + total_nutrients.get("NA", 0) +
              total_nutrients.get("ZN", 0)
          ),
          "Minerals - Secondary": (
              total_nutrients.get("AS", 0) + total_nutrients.get("HG", 0) + total_nutrients.get("SE", 0)
          ),
          "Fatty acid profile - Saturated": total_nutrients.get("FASAT", 0),
          "Fatty acid profile - Unsaturated": (
              total_nutrients.get("FAMS", 0) + total_nutrients.get("FAPU", 0)
          ),
          "Cholesterol": total_nutrients.get("CHOLC", 0)
      }

def ingredient_distributed_nutrients_collection(ingredient_nutrients):
  return {
            "Macro nutrients - Energy": ingredient_nutrients.get("ENERC", 0),
            "Macro nutrients - Carbs": ingredient_nutrients.get("CHOAVLDF", 0),
            "Macro nutrients - Proteins": ingredient_nutrients.get("PROTCNT", 0),
            "Macro nutrients - Fats": ingredient_nutrients.get("FATCE", 0),
            "Macro nutrients - Fibers": ingredient_nutrients.get("FIBTG", 0),
            "Water soluble Vitamin - Primary": sum(
                ingredient_nutrients.get(key, 0) for key in ["THIA", "RIBF", "NIA", "PANTAC", "VITB6C", "VITC"]
            ),
            "Water soluble Vitamin - Secondary": sum(
                ingredient_nutrients.get(key, 0) for key in ["BIOT", "FOLSUM"]
            ),
            "Fat soluble Vitamin - Primary": sum(
                ingredient_nutrients.get(key, 0) for key in ["RETOL", "ERGCAL", "CHOCAL", "VITK1", "VITK2", "CARTOID"]
            ),
            "Fat soluble Vitamin - Secondary": ingredient_nutrients.get("VITE", 0),
            "Minerals - Primary": sum(
                ingredient_nutrients.get(key, 0) for key in ["AL", "CD", "CA", "CR", "CO", "CU", "FE", "PB", "LI", "MG", "MN", "MO", "NI", "P", "K", "NA", "ZN"]
            ),
            "Minerals - Secondary": sum(
                ingredient_nutrients.get(key, 0) for key in ["AS", "HG", "SE"]
            ),
            "Fatty acid profile - Saturated": ingredient_nutrients.get("FASAT", 0),
            "Fatty acid profile - Unsaturated": sum(
                ingredient_nutrients.get(key, 0) for key in ["FAMS", "FAPU"]
            ),
            "Cholesterol": ingredient_nutrients.get("CHOLC", 0)
          }

def get_ingredient_name_from_db(simentic_search_result):
    simentic_search = simentic_search_result.page_content
    simentic_search = normalize_spaces(simentic_search)
    return simentic_search

nutrient_info_list = []

def calculate_nutrients(ingredient_name, quantity_g, retriever):
    logger.info(f"Calculating nutrients for {quantity_g} g of {ingredient_name}...")

        # Fetch the semantic search result
    simentic_search_result = retriever.invoke(ingredient_name)
    if not simentic_search_result:
        logging.warning(f"Ingredient not found in semantic search: {ingredient_name}")
        return None

    for search_data in simentic_search_result:
        
        simentic_search = get_ingredient_name_from_db(search_data)
        nutrient_data = nutrients_collection.find_one({"Food name": simentic_search})

        if nutrient_data:
            nutrient_info = f"Ingredient Name: {ingredient_name}, Found Ingredient: {nutrient_data.get('Food Name')}, Food Code: {nutrient_data.get('Foodcode')}"
            nutrient_info_list.append(nutrient_info)  # Append to the list
            break

    if not nutrient_data:
        logging.warning(f"No nutrient data found for {ingredient_name} ({simentic_search}).")
        return None
    
    logging.debug(f"Nutrient data retrieved for {ingredient_name}: {nutrient_data}")



    nutrients_result = {}
    for nutrient, value in nutrient_data.items():
        if nutrient in ["_id", "Food name", "Foodcode"]:
            continue

        try:
            base_value = float(value) if value else 0
        except (ValueError, TypeError):
            logger.warning(f"Value for {nutrient} is not a valid number: {value} (ingredient: {ingredient_name})")
            base_value = 0
            continue



        if not is_indian_id(nutrient_data['Foodcode']):
            if nutrient == "ENERC":
              base_value = base_value * 0.239

        else:
            if nutrient == "CR" or nutrient == "CO" or nutrient == "MO" or nutrient == "NI" or nutrient == "FASAT" or nutrient == "FAMS" or nutrient == "FAPU":

              base_value = base_value * 0.001


        try:
            quantity_g = float(quantity_g)
            if quantity_g <= 0:
                logger.warning(f"Invalid quantity {quantity_g} for {ingredient_name}. Using default value of 1g.")
                quantity_g = 1
        except (ValueError, TypeError):
            logger.warning(f"Invalid quantity {quantity_g} for {ingredient_name}. Using default value of 1g.")
            quantity_g = 1



        logger.debug(f"Calculating {nutrient} with base_value: {base_value} and quantity_g: {quantity_g}")
        nutrients_result[nutrient] = round((base_value * quantity_g) / 100, 2)
        logger.debug(f"Calculated {nutrient}: {nutrients_result[nutrient]}")

    return nutrients_result
def calculate_ingredient_nutrient_percentages(ingredients_nutrient_contribution, nutrient_distribution, logger):
    ingredient_nutrient_percentages = {}

    for item in ingredients_nutrient_contribution:
        for ingredient, nutrients in item.items():
            ingredient_percentages = {}
            for nutrient, value in nutrients.items():
                if nutrient in nutrient_distribution and nutrient_distribution[nutrient] != 0:
                    percentage = (value / nutrient_distribution[nutrient]) * 100
                    ingredient_percentages[nutrient] = round(percentage, 2)

            # Save the calculated percentages for the current ingredient
            ingredient_nutrient_percentages[ingredient] = ingredient_percentages

            # Log the nutrient percentages
            logger.debug("Nutrient percentages for %s: %s", ingredient, ingredient_percentages)

    return ingredient_nutrient_percentages

def nutrient_categorize_contribution(percentage: float):
    if percentage >= 33:
        return 'Essential - Core'
    elif 20 <= percentage < 33:
        return 'Primary'
    elif 5 <= percentage < 20:
        return 'Secondary'
    else:
        return 'Flexible'

def quantity_categorize_contribution(percentage: float):
    if percentage > 35:
        return 'Essential - Core'
    elif 15 < percentage <= 35:
        return 'Primary'
    return None


def optimize_ingredient_categorization(dishdes_ingredients_list, ingredient_nutrient_categories, ingredient_quantity_categories):
    essential = []
    primary = []
    secondary = []
    flexible = []

    if dishdes_ingredients_list:
        for i in dishdes_ingredients_list:
            essential.append(i)


    if ingredient_quantity_categories["Essential - Core"]:
        for i in ingredient_quantity_categories["Essential - Core"]:
            if i not in essential:
                if i not in primary:
                    ingredient_quantity_categories['Primary'].append(i)

    if ingredient_nutrient_categories['Essential - Core']:
        for i in ingredient_nutrient_categories['Essential - Core']:
            if i not in essential:
                    if i not in primary:
                        ingredient_nutrient_categories['Primary'].append(i)

    if ingredient_quantity_categories['Primary']:
        for i in ingredient_quantity_categories['Primary']:
            if i not in essential:
                if i not in primary:
                    if i in ingredient_nutrient_categories['Primary']:
                        primary.append(i)
                    else:
                        secondary.append(i)

    if ingredient_nutrient_categories['Primary']:
        for i in ingredient_nutrient_categories['Primary']:
            if i not in essential:
                if i not in primary:
                    secondary.append(i)

    if ingredient_nutrient_categories['Secondary']:
        for i in ingredient_nutrient_categories['Secondary']:
            if i not in essential:
                if i not in primary:
                    if i not in secondary:
                        secondary.append(i)

    if ingredient_nutrient_categories['Flexible']:
        for i in ingredient_nutrient_categories['Flexible']:
            if i not in essential:
                if i not in primary:
                    if i not in secondary:
                            flexible.append(i)
    return essential, primary, secondary, flexible


def calculate_ingredient_percentages(ingredients_nutrient_contribution, nutrient_distribution):
    ingredient_nutrient_percentages = {}
    for item in ingredients_nutrient_contribution:
        for ingredient, nutrients in item.items():
            ingredient_percentages = {}
            for nutrient, value in nutrients.items():
                if nutrient in nutrient_distribution and nutrient_distribution[nutrient] != 0:
                    percentage = (value / nutrient_distribution[nutrient]) * 100
                    ingredient_percentages[nutrient] = round(percentage, 2)
            if ingredient_percentages:
                ingredient_nutrient_percentages[ingredient] = ingredient_percentages
    return ingredient_nutrient_percentages

def categorize_ingredients_by_nutrients(ingredient_nutrient_percentages):
    ingredient_nutrient_categories = {"Essential - Core": [], "Primary": [], "Secondary": [], "Flexible": []}
    for ingredient in ingredient_nutrient_percentages:
        ingredient_highest_percentage = max(ingredient_nutrient_percentages[ingredient].values())
        category = nutrient_categorize_contribution(ingredient_highest_percentage)
        ingredient_nutrient_categories[category].append(ingredient)
    return ingredient_nutrient_categories

def categorize_ingredients_by_quantity(ingredients_list, serving_size):
    ingredient_quantity_categories = {"Essential - Core": [], "Primary": []}
    ingredient_quantity_percentages = {}
    for item in ingredients_list:
        ingredient_name = item.get("name")
        quantity_g = item.get("quantity", 0)
        quantity_g_float = float(quantity_g)    # to taste error solve

        try:
            # Check if quantity_g is 'to taste' and assign default value if true
            if quantity_g == 'to taste':
                quantity_g_float = 5.0
            else:
                quantity_g_float = float(quantity_g)
        except ValueError as e:
            # Handle other unexpected errors
            quantity_g_float = 5.0  # Assign default value as fallback


        serving_size_float = float(serving_size) if serving_size else 0
        percentage = (quantity_g_float / serving_size_float) * 100 if serving_size_float != 0 else 0

        ingredient_quantity_percentages[ingredient_name] = round(percentage, 2)

    for ingredient, percentage in ingredient_quantity_percentages.items():
        category = quantity_categorize_contribution(percentage)
        if category:
            ingredient_quantity_categories[category].append(ingredient)

    return ingredient_quantity_categories

def adjust_quantities_with_min_max(dish):
    #   print(json.dumps(dish, indent=4))

      adjustments = {
      "essential": [10, 5],  # +10%, -5%
      "primary": [15, 15],   # +/-15%
      "secondary": [30, 30], # +/-30%
      "flexible": [50, 50]   # +/-50%
      }

      logger.debug(f"Final AI data categories: {dish['categories']}")

      category =  dish["categories"]

      categories = dish.get("categories", {})  

      ingredients = dish.get("dish_variants", {}).get("normal", {}).get("full", {}).get("ingredients", [])
      # Create a mapping of ingredient names to their categories
      ingredient_categories = {}
      for category, ingredient_list in categories.items():
          for ingredient in ingredient_list:
              ingredient_categories[ingredient] = category

      # Add min_value and max_value to each ingredient
      for ingredient in ingredients:
          name = ingredient.get("name")
          original_quantity = float(ingredient.get("quantity", 0))
          if name in ingredient_categories:
              category = ingredient_categories[name]
              max_increase, max_decrease = adjustments.get(category, [0, 0])

              # Calculate the range of allowable adjustments
              min_value = round(original_quantity * (1 - max_decrease / 100), 2)
              max_value = round(original_quantity * (1 + max_increase / 100), 2)

              # Add min_value and max_value to the ingredient
              ingredient["min_value"] = min_value
              ingredient["max_value"] = max_value

              logger.info(
                  f"Updated {name} ({category}): Quantity: {original_quantity}, Min: {min_value}, Max: {max_value}"
              )
    #   print(json.dumps(dish, indent=4))
      return dish

def get_prior_ingredients_from_model3(dish):
      
      # Extract ingredients from dish name and description
      dish_name = dish['dish_name']
      logger.info(f"Starting to process prior ingredients for dish: {dish_name}")

      dish_descprition = dish['dish_description']
      ingredients_list = dish['dish_variants']['normal']['full']['ingredients']

      dishdes_ingredients_list = extract_ingredients(dish_name, dish_descprition, ingredients_list)

      ingredients_nutrient_contribution = []

      # Process each ingredient in the list
      for item in ingredients_list:
          logger.debug("Processing ingredient: %s", item)
          ingredient_name = item.get("name")
          quantity_g = item.get("quantity", 0)
          logger.debug(f"Processing ingredient: {ingredient_name} with quantity: {quantity_g} g")

          # Calculate nutrients for the ingredient
          ingredient_nutrients = calculate_nutrients(ingredient_name, quantity_g, ingredient_retriever)

          if ingredient_nutrients:
            logger.debug(f"Nutrient data for {ingredient_name}: {ingredient_nutrients}")
          else:
              logger.warning(f"No nutrient data found for {ingredient_name}")
              continue

          # Distribute the nutrients across the ingredient
          ingredient_distributed_nutrients = ingredient_distributed_nutrients_collection(ingredient_nutrients)
          ingredients_nutrient_contribution.append({ingredient_name: ingredient_distributed_nutrients})

          # Add to the total nutrient values
          for nutrient, value in ingredient_nutrients.items():
            total_nutrients[nutrient] = round(total_nutrients.get(nutrient, 0) + value, 2)

      logger.debug(f"Total nutrients accumulated: {total_nutrients}")

      # Get nutrient distribution
      nutrient_distribution = nutrient_distribution_collection(total_nutrients)
      logger.debug(f"Nutrient distribution: {nutrient_distribution}")

      # Calculate ingredient nutrient percentages
      ingredient_nutrient_percentages = calculate_ingredient_percentages(ingredients_nutrient_contribution, nutrient_distribution)
      logger.debug("Nutrient percentages: %s", ingredient_nutrient_percentages)

      # Categorize ingredients by quantity
      dish_variants = dish['dish_variants']['normal']['full']
      serving_size = dish_variants['serving']['size']

    #   serving_size = dish.get('serving_size')
    
      ingredient_quantity_categories = categorize_ingredients_by_quantity(ingredients_list, serving_size)
      logger.debug(f"Ingredient quantity categories: {ingredient_quantity_categories}")

    # Categorize ingredients by their nutrient contributions
      ingredient_nutrient_categories = categorize_ingredients_by_nutrients(ingredient_nutrient_percentages)
      logger.debug(f"Ingredient nutrient categories: {ingredient_nutrient_categories}")

      # Optimize ingredient categorizations
      essential, primary, secondary, flexible = optimize_ingredient_categorization(dishdes_ingredients_list, ingredient_nutrient_categories, ingredient_quantity_categories)
      logger.info(f"Optimized categories: Essential: {essential}, Primary: {primary}, Secondary: {secondary}, Flexible: {flexible}")

      # Update the AI data with the optimized categories
      dish["categories"] = {
          "essential": essential,
          "primary": primary,
          "secondary": secondary,
          "flexible": flexible
      }

      return dish["categories"]



