
from datetime import datetime
import json
import logging
from http.client import HTTPException
import re
from django.http import JsonResponse
from pinecone import Pinecone
from pinecone_text.sparse import BM25Encoder
from langchain_community.retrievers import PineconeHybridSearchRetriever
from langchain_huggingface import HuggingFaceEmbeddings

from fitshield_webapp.AI.AIModel.model_helpers.validate_format import normalize_spaces
from fitshield_webapp.view.restro.save_json import save_json_to_file

# from fitshield_webapp.view.user.allergy_management import get_allergy_categories
from .model_helpers.initialize_nutrients_unit import nutrient_units, total_nutrients
from config.connection import db

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',  
    handlers=[
        logging.StreamHandler()  
    ]
)
logger = logging.getLogger(__name__)

converse = db["Unitconversion"]
nutrients_collection = db["Nutrients"]

# Pinecone Configuration
api_key = "c2468019-302c-411e-bf36-c802d54d7a87"
unit_index_name = "hybrid-search-langchain-unitconversion"
ingredient_index_name = "hybrid-search-langchain-pincone"

pc = Pinecone(api_key=api_key)
unit_index = pc.Index(unit_index_name)
ingredient_index = pc.Index(ingredient_index_name)

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


from pathlib import Path


# Load allergen map from the JSON file
base_dir = Path(__file__).resolve().parent
allergen_file_path = base_dir / "User" / "allergen_data.json"

with open(allergen_file_path, "r") as f:
    ingredient_allergen_map = json.load(f)
    
def normalize_string(input_string):
    """Normalize a string by removing extra spaces and converting to lowercase."""
    return " ".join(input_string.lower().strip().split())

def get_allergy_categories(ingredient_name):
    """Get allergy categories for a specific ingredient."""
    categories = set()
    normalized_ingredient = normalize_string(ingredient_name)  # Normalize the ingredient name
    
    for entry in ingredient_allergen_map:
        for mapped_ingredient in entry["Ingredient_Name"].split(","):
            normalized_allergen = normalize_string(mapped_ingredient)  # Normalize each allergen
            
            if normalized_allergen in normalized_ingredient:  # Check if allergen is part of ingredient
                categories.add(entry["Allergy_category"])
    return list(categories)


# Get the current working directory (you can also use environment variables)
base_dir = Path(__file__).resolve().parent  # E:\Fitshield\ftishield\fitshield_webapp\AI\AIModel

ingredients_bm25_path = base_dir / "data" / "ingredients_bm25_values.json"
unit_bm25_path = base_dir / "data" / "unit_bm25_values.json"

print(f"Ingredients Path: {ingredients_bm25_path}")
print(f"Unit Path: {unit_bm25_path}")

ingredient_bm25_encoder = BM25Encoder().load(str(ingredients_bm25_path))
unit_bm25_encoder = BM25Encoder().load(str(unit_bm25_path))

unit_retriever = PineconeHybridSearchRetriever(
    embeddings=embeddings, sparse_encoder=unit_bm25_encoder, index=unit_index
)
ingredient_retriever = PineconeHybridSearchRetriever(
    embeddings=embeddings, sparse_encoder=ingredient_bm25_encoder, index=ingredient_index
)
logger.info("Pinecone setup complete!")
logger.info("Step 1 Completed")


def is_indian_id(id_value):

    id_value = str(id_value)
    # Check if the ID meets all conditions
    return (
        len(id_value) == 4 and             # Condition 1: Length is 4
        id_value[0].isupper() and          # Condition 2: Starts with a capital letter
        id_value[1:].isalnum()             # Condition 3: Remaining characters are numeric
    )


# Function to convert ml to grams based on density
def convert_ml_to_g(ingredient_name, quantity_ml, retriever):
    try:
        logging.debug(f"Starting conversion of {quantity_ml} ml of {ingredient_name} to grams.")
        
        # Perform semantic search to find the ingredient
        simentic_search = retriever.invoke(ingredient_name)[0].page_content
        logging.info(f"Semantic search result for {ingredient_name}: {simentic_search}")
        
        # Query the database for density data
        query = {"ingredient": simentic_search}
        density_data = converse.find_one(query)
        
        if density_data:
            logging.debug(f"Density data found: {density_data}")
        else:
            logging.warning(f"No density data found in the database for ingredient: {ingredient_name}")
        
        # Perform the conversion
        if density_data and "density" in density_data:
            density = density_data["density"]  # density is in g/mL
            quantity_g = quantity_ml * density
            logging.info(f"Converted {quantity_ml} ml of {ingredient_name} to {quantity_g} g using density {density}.")
            return quantity_g
        else:
            logging.error(f"Density data not found or incomplete for ingredient: {ingredient_name}")
            return None
    
    except Exception as e:
        logging.exception(f"An error occurred while converting {ingredient_name}: {e}")
        return None

def get_ingredient_name_from_db(simentic_search_result):
    simentic_search = simentic_search_result.page_content
    simentic_search = normalize_spaces(simentic_search)
    return simentic_search

nutrient_info_list = []

def calculate_nutrients(ingredient_name, quantity_g, retriever):
    try:
        logging.debug(f"Starting nutrient calculation for {ingredient_name}, quantity: {quantity_g}g.")
        
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
                print(f"Ingredient name: {ingredient_name}, Found : {nutrient_data.get('Food name')}, Food Code: {nutrient_data.get('Foodcode')}")
                break

        if not nutrient_data:
            logging.warning(f"No nutrient data found for {ingredient_name} ({simentic_search}).")
            return None
        
        logging.debug(f"Nutrient data retrieved for {ingredient_name}: {nutrient_data}")

        nutrients_result = {}

        # Iterate over all nutrient fields
        for nutrient, value in nutrient_data.items():
            if nutrient in ["_id", "Food name", "Foodcode"]:
                continue  # Skip non-nutrient fields
            
            try:
                base_value = float(value) if value else 0.0
            except ValueError:
                logging.error(f"Invalid nutrient value for {nutrient} in {ingredient_name}: {value}")
                base_value = 0.0

            # Adjust units for non-Indian and specific nutrients
            if is_indian_id(nutrient_data['Foodcode']):
                if nutrient == "ENERC":
                    base_value *= 0.239  # Energy conversion
            else:
                if nutrient in ["CR", "CO", "MO", "NI", "FASAT", "FAMS", "FAPU"]:
                    base_value *= 0.001  # Convert to appropriate units

            # Calculate nutrient value for the given quantity
            calculated_value = (base_value * quantity_g) / 100
            nutrients_result[nutrient] = round(calculated_value, 2)
            logging.debug(f"Nutrient {nutrient}: {calculated_value} (base: {base_value}, quantity: {quantity_g}g)")

        logging.info(f"Completed nutrient calculation for {ingredient_name}. Result: {nutrients_result}")
        return nutrients_result

    except Exception as e:
        logging.exception(f"An error occurred while calculating nutrients for {ingredient_name}: {e}")
        return None


cooking_methods = {
    "Boiling": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.50 * (temp - 100) + 10.0 * (t - 5)) / 100)),
            "fatty_acid_profile": lambda t, temp: 1.00,  # Fixed retention
            "carbs": lambda t, temp: 1.00,  # Fixed retention
            "water_soluble_vitamin": lambda t, temp: min(0.70, max(0.50, (70 - 0.2 * (temp - 100)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: 0.90,  # Fixed retention
            "minerals": lambda t, temp: min(0.90, max(0.70, (90 - 0.1 * (temp - 100)) / 100))
        }
    },
    "Broiling": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.50 * (temp - 100) + 10.0 * (t - 5)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.50, max(1.00, (100 + 1.0 * (temp - 150) + 2.0 * (t - 5)) / 100)),
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 2.50 * (temp - 175) + 20.0 * (t - 5)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.90, max(0.45, (90 - 0.2 * (temp - 100) + 0.5 * (t - 5)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.80, (95 - 0.1 * (temp - 100) + 0.3 * (t - 5)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.70, (95 - 0.15 * (temp - 100) + 0.4 * (t - 5)) / 100))
        }
    },
    "Grilling": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.50 * (temp - 100) + 10.0 * (t - 5)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.50, max(1.00, (100 + 1.0 * (temp - 150) + 2.0 * (t - 5)) / 100)),
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 2.50 * (temp - 175) + 20.0 * (t - 5)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.90, max(0.45, (90 - 0.2 * (temp - 100) + 0.5 * (t - 5)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.80, (95 - 0.1 * (temp - 100) + 0.3 * (t - 5)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.70, (95 - 0.15 * (temp - 100) + 0.4 * (t - 5)) / 100))
        }
    },
    "Steaming": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 100) + 5.0 * (t - 5)) / 100)),
            "fatty_acid_profile": lambda t, temp: 1.00,  # Fixed retention
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 1.5 * (temp - 100) + 10.0 * (t - 5)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.90, max(0.75, (90 - 0.25 * (temp - 100) + 0.3 * (t - 5)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.90, (95 - 0.1 * (temp - 100) + 0.2 * (t - 5)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.90, (95 - 0.15 * (temp - 100) + 0.2 * (t - 5)) / 100))
        }
    },
    "Sautéing": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 150) + 5.0 * (t - 3)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.30, max(1.10, (100 + 0.5 * (temp - 150) + 2.0 * (t - 3)) / 100)),  # Fats slightly increase due to oil absorption
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 1.5 * (temp - 150) + 3.0 * (t - 3)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.85, max(0.70, (85 - 0.3 * (temp - 150) + 0.4 * (t - 3)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.90, (95 - 0.1 * (temp - 150) + 0.2 * (t - 3)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.85, (95 - 0.15 * (temp - 150) + 0.3 * (t - 3)) / 100))
        }
    },
    "Stir-frying": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 150) + 5.0 * (t - 3)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.30, max(1.10, (100 + 0.5 * (temp - 150) + 2.0 * (t - 3)) / 100)),  # Fats slightly increase due to oil absorption
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 1.5 * (temp - 150) + 3.0 * (t - 3)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.85, max(0.70, (85 - 0.3 * (temp - 150) + 0.4 * (t - 3)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.90, (95 - 0.1 * (temp - 150) + 0.2 * (t - 3)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.85, (95 - 0.15 * (temp - 150) + 0.3 * (t - 3)) / 100))
        }
    },
    "Microwaving": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 2.0 * (temp - 40) + 8.0 * (t - 1)) / 100)),
            "fatty_acid_profile": lambda t, temp: 1.00,  # Fixed retention
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 40) + 5.0 * (t - 1)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.90, max(0.60, (90 - 0.3 * (temp - 40) + 0.4 * (t - 1)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.90, (95 - 0.2 * (temp - 40) + 0.3 * (t - 1)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.90, (95 - 0.25 * (temp - 40) + 0.4 * (t - 1)) / 100))
        }
    },
    "Baking": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 160) + 5.0 * (t - 15)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.00, max(0.90, (100 - 0.5 * (temp - 160) + 1.0 * (t - 15)) / 100)),
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 2.0 * (temp - 160) + 10.0 * (t - 15)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.85, max(0.50, (85 - 0.4 * (temp - 160) + 0.5 * (t - 15)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.80, (95 - 0.3 * (temp - 160) + 0.4 * (t - 15)) / 100)),
            "minerals": lambda t, temp: min(0.90, max(0.80, (90 - 0.2 * (temp - 160) + 0.3 * (t - 15)) / 100))
        }
    },
    "Roasting": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 160) + 5.0 * (t - 15)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.00, max(0.90, (100 - 0.5 * (temp - 160) + 1.0 * (t - 15)) / 100)),
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 2.0 * (temp - 160) + 10.0 * (t - 15)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.85, max(0.50, (85 - 0.4 * (temp - 160) + 0.5 * (t - 15)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.80, (95 - 0.3 * (temp - 160) + 0.4 * (t - 15)) / 100)),
            "minerals": lambda t, temp: min(0.90, max(0.80, (90 - 0.2 * (temp - 160) + 0.3 * (t - 15)) / 100))
        }
    },
    "Frying": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 175) + 3.0 * (t - 5)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.50, max(1.10, (100 + 1.0 * (temp - 175) + 2.0 * (t - 5)) / 100)),
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 2.0 * (temp - 175) + 5.0 * (t - 5)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.75, max(0.55, (75 - 0.3 * (temp - 175) + 0.4 * (t - 5)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.90, max(0.80, (90.00 - 0.20 * (temp - 175) + 0.30 * (t - 5)) / 100)),
            "minerals": lambda t, temp: min(0.90, max(0.80, (90.00 - 0.20 * (temp - 175) + 0.40 * (t - 5)) / 100))
        }
    },
    "Deep Frying": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 175) + 3.0 * (t - 5)) / 100)),
            "fatty_acid_profile": lambda t, temp: min(1.50, max(1.10, (100 + 1.0 * (temp - 175) + 2.0 * (t - 5)) / 100)),
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 2.0 * (temp - 175) + 5.0 * (t - 5)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.75, max(0.55, (75 - 0.3 * (temp - 175) + 0.4 * (t - 5)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.90, max(0.80, (90.00 - 0.20 * (temp - 175) + 0.30 * (t - 5)) / 100)),
            "minerals": lambda t, temp: min(0.90, max(0.80, (90.00 - 0.20 * (temp - 175) + 0.40 * (t - 5)) / 100))
        }
    },
    "Slow Cooking": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 0.5 * (temp - 70) + 1.0 * (t - 4)) / 100)),
            "fatty_acid_profile": lambda t, temp: 1.00,  # Fixed retention
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 0.3 * (temp - 70) + 0.5 * (t - 4)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.75, max(0.55, (75 - 0.3 * (temp - 70) + 0.4 * (t - 4)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.90, max(0.80, (90 - 0.2 * (temp - 70) + 0.3 * (t - 4)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.85, (95 - 0.15 * (temp - 70) + 0.2 * (t - 4)) / 100))
        }
    },
    "Pressure Cooking": {
        "retention": {
            "proteins": lambda t, temp: min(1.00, max(0.95, (100 - 1.0 * (temp - 110) + 2.0 * (t - 5)) / 100)),
            "fatty_acid_profile": lambda t, temp: 1.00,  # Fixed retention
            "carbs": lambda t, temp: min(1.00, max(0.95, (100 - 0.5 * (temp - 110) + 1.0 * (t - 5)) / 100)),
            "water_soluble_vitamin": lambda t, temp: min(0.85, max(0.70, (85 - 0.4 * (temp - 110) + 0.3 * (t - 5)) / 100)),
            "fat_soluble_vitamin": lambda t, temp: min(0.95, max(0.85, (95 - 0.3 * (temp - 110) + 0.2 * (t - 5)) / 100)),
            "minerals": lambda t, temp: min(0.95, max(0.90, (95 - 0.2 * (temp - 110) + 0.1 * (t - 5)) / 100))
        }
    }
}

distributed_nutrients_list = {
    "water_soluble_vitamin": ["THIA","RIBF","NIA","PANTAC","VITB6C","VITC","BIOT","FOLSUM"],
    "fat_soluble_vitamin": ["RETOL","ERGCAL","CHOCAL","VITK1","VITK2","CARTOID","VITE"],
    "minerals": ["AL","CD","CA","CR","CO","CU","FE","PB","LI","MG","MN","MO","NI","P","K","NA","ZN","AS","HG","SE"],
    "fatty_acid_profile": ["FASAT","FAMS","FAPU"]
}

def apply_cooking_retention(total_nutrients, cooking_method, cooking_time, cooking_temperature):
    try:
        logging.info(f"Applying cooking retention for method: {cooking_method}, time: {cooking_time} minutes, temperature: {cooking_temperature}°C.")
        
        logging.debug(f"Initial total nutrients: {total_nutrients}")
        logging.debug(f"Available cooking methods: {cooking_methods}")

        # Validate cooking method
        if cooking_method not in cooking_methods:
            
            total_nutrients["ENERC"] = (
                    total_nutrients.get("FIBTG", 0) * 2  # Fiber
                    + total_nutrients.get("CHOAVLDF", 0) * 4  # Carbs
                    + total_nutrients.get("PROTCNT", 0) * 4  # Protein
                    + total_nutrients.get("FATCE", 0) * 9  # Fat
                )
            logging.error(f"Unknown cooking method: {cooking_method}")
            return total_nutrients

        method_data = cooking_methods[cooking_method]
        retention = method_data["retention"]
        logging.debug(f"Retention factors for method '{cooking_method}': {retention}")

        # Apply retention for proteins
        if "proteins" in retention:
            proteins_retention = retention["proteins"](cooking_time, cooking_temperature)
            if "PROTCNT" in total_nutrients:
                total_nutrients["PROTCNT"] = round(total_nutrients["PROTCNT"] * proteins_retention, 2)
                logging.info(f"Protein (PROTCNT) after retention: {total_nutrients['PROTCNT']} (retention factor: {proteins_retention})")

        # Apply retention for carbs
        if "carbs" in retention:
            carbs_retention = retention["carbs"](cooking_time, cooking_temperature)
            if "CHOAVLDF" in total_nutrients:
                total_nutrients["CHOAVLDF"] = round(total_nutrients["CHOAVLDF"] * carbs_retention, 2)
                logging.info(f"Carbs (CHOAVLDF) after retention: {total_nutrients['CHOAVLDF']} (retention factor: {carbs_retention})")

        # Apply retention for fats
        if "fatty_acid_profile" in retention:
            fats_retention = retention["fatty_acid_profile"](cooking_time, cooking_temperature)
            if "FATCE" in total_nutrients:
                total_nutrients["FATCE"] = round(total_nutrients["FATCE"] * fats_retention, 2)
                logging.info(f"Fats (FATCE) after retention: {total_nutrients['FATCE']} (retention factor: {fats_retention})")

        # Apply retention for other nutrient groups
        for nutrient_group, nutrients in distributed_nutrients_list.items():
            if nutrient_group in retention:
                retention_factor = retention[nutrient_group](cooking_time, cooking_temperature)
                logging.debug(f"Retention factor for {nutrient_group}: {retention_factor}")
                for nutrient in nutrients:
                    if nutrient in total_nutrients:
                        total_nutrients[nutrient] = round(total_nutrients[nutrient] * retention_factor, 2)
                        logging.info(f"Nutrient {nutrient} after retention: {total_nutrients[nutrient]}")

        # Recalculate total energy (ENERC)
        total_nutrients["ENERC"] = (
            total_nutrients.get("FIBTG", 0) * 2  # Fiber
            + total_nutrients.get("CHOAVLDF", 0) * 4  # Carbs
            + total_nutrients.get("PROTCNT", 0) * 4  # Protein
            + total_nutrients.get("FATCE", 0) * 9  # Fat
        )
        logging.info(f"Total energy (ENERC) after retention: {total_nutrients['ENERC']}")

        logging.debug(f"Final total nutrients: {total_nutrients}")
        return total_nutrients

    except Exception as e:
        logging.error(f"Error in apply_cooking_retention: {str(e)}", exc_info=True)
        raise

def distribute_nutrients(total_nutrients):
    return {
        "macro_nutrients": [
        {"name": "energy", "value": total_nutrients.get("ENERC", 0.0), "unit": "kcal"},
        {"name": "carbs", "value": total_nutrients.get("CHOAVLDF", 0.0), "unit": "g"},
        {"name": "proteins", "value": total_nutrients.get("PROTCNT", 0.0), "unit": "g"},
        {"name": "fats", "value": total_nutrients.get("FATCE", 0.0), "unit": "g"},
        {"name": "fibers", "value": total_nutrients.get("FIBTG", 0.0), "unit": "g"},
        ],
        "water_soluble_vitamin": [
            {"name": "thiamin", "value": total_nutrients.get("THIA", 0.0), "unit": "mg"},
            {"name": "riboflavin", "value": total_nutrients.get("RIBF", 0.0), "unit": "mg"},
            {"name": "niacin", "value": total_nutrients.get("NIA", 0.0), "unit": "mg"},
            {"name": "vitamin_b5", "value": total_nutrients.get("PANTAC", 0.0), "unit": "mg"},
            {"name": "vitamin_b6", "value": total_nutrients.get("VITB6C", 0.0), "unit": "mg"},
            {"name": "vitamin_c", "value": total_nutrients.get("VITC", 0.0), "unit": "mg"},
            {"name": "biotin", "value": total_nutrients.get("BIOT", 0.0), "unit": "µg"},
            {"name": "folate", "value": total_nutrients.get("FOLSUM", 0.0), "unit": "µg"},
        ],
        "fat_soluble_vitamin": [
            {"name": "vitamin_a", "value": total_nutrients.get("RETOL", 0.0), "unit": "µg"},
            {"name": "vitamin_d2", "value": total_nutrients.get("ERGCAL", 0.0), "unit": "µg"},
            {"name": "vitamin_d3", "value": total_nutrients.get("CHOCAL", 0.0), "unit": "µg"},
            {"name": "vitamin_k1", "value": total_nutrients.get("VITK1", 0.0), "unit": "µg"},
            {"name": "vitamin_k2", "value": total_nutrients.get("VITK2", 0.0), "unit": "µg"},
            {"name": "carotenoids", "value": total_nutrients.get("CARTOID", 0.0), "unit": "µg"},
            {"name": "vitamin_e", "value": total_nutrients.get("VITE", 0.0), "unit": "mg"},
        ],
        "minerals": [
            {"name": "aluminium", "value": total_nutrients.get("AL", 0.0), "unit": "mg"},
            {"name": "cadmium", "value": total_nutrients.get("CD", 0.0), "unit": "mg"},
            {"name": "calcium", "value": total_nutrients.get("CA", 0.0), "unit": "mg"},
            {"name": "chromium", "value": total_nutrients.get("CR", 0.0), "unit": "mg"},
            {"name": "cobalt", "value": total_nutrients.get("CO", 0.0), "unit": "mg"},
            {"name": "copper", "value": total_nutrients.get("CU", 0.0), "unit": "mg"},
            {"name": "iron", "value": total_nutrients.get("FE", 0.0), "unit": "mg"},
            {"name": "lead", "value": total_nutrients.get("PB", 0.0), "unit": "mg"},
            {"name": "lithium", "value": total_nutrients.get("LI", 0.0), "unit": "mg"},
            {"name": "magnesium", "value": total_nutrients.get("MG", 0.0), "unit": "mg"},
            {"name": "manganese", "value": total_nutrients.get("MN", 0.0), "unit": "mg"},
            {"name": "molybdenum", "value": total_nutrients.get("MO", 0.0), "unit": "mg"},
            {"name": "nickel", "value": total_nutrients.get("NI", 0.0), "unit": "mg"},
            {"name": "phosphorus", "value": total_nutrients.get("P", 0.0), "unit": "mg"},
            {"name": "potassium", "value": total_nutrients.get("K", 0.0), "unit": "mg"},
            {"name": "sodium", "value": total_nutrients.get("NA", 0.0), "unit": "mg"},
            {"name": "zinc", "value": total_nutrients.get("ZN", 0.0), "unit": "mg"},
            {"name": "arsenic", "value": total_nutrients.get("AS", 0.0), "unit": "µg"},
            {"name": "mercury", "value": total_nutrients.get("HG", 0.0), "unit": "µg"},
            {"name": "selenium", "value": total_nutrients.get("SE", 0.0), "unit": "µg"},
        ],
        "fatty_acid_profile": [
            {"name": "total_saturated_fats", "value": total_nutrients.get("FASAT", 0.0), "unit": "mg"},
            {"name": "total_monounsaturated_fats", "value": total_nutrients.get("FAMS", 0.0), "unit": "mg"},
            {"name": "total_polyunsaturated_fats", "value": total_nutrients.get("FAPU", 0.0), "unit": "mg"},
        ],
        "cholesterol": [
            {"name": "cholesterol", "value": total_nutrients.get("CHOLC", 0.0), "unit": "mg"},
        ],
        "sugar": [
            {"name": "total_carbohydrates", "value": total_nutrients.get("TCHO", 0.0), "unit": "g"},
            {"name": "starch", "value": total_nutrients.get("STARCH", 0.0), "unit": "g"},
            {"name": "fructose", "value": total_nutrients.get("FRUS", 0.0), "unit": "g"},
            {"name": "glucose", "value": total_nutrients.get("GLUS", 0.0), "unit": "g"},
            {"name": "sucrose", "value": total_nutrients.get("SUCS", 0.0), "unit": "g"},
            {"name": "maltose", "value": total_nutrients.get("MALS", 0.0), "unit": "g"},
            {"name": "total_free_sugars", "value": total_nutrients.get("TOTALFREESUGARS", 0.0), "unit": "g"},
        ],
        "other": [
            {"name": "total_minerals", "value": total_nutrients.get("ASH", 0.0), "unit": "g"},
            {"name": "soluble_fiber", "value": total_nutrients.get("FIBSOL", 0.0), "unit": "g"},
            {"name": "insoluble_fiber", "value": total_nutrients.get("FIBINS", 0.0), "unit": "g"},
        ],
    }

def process_ingredients_nutrients_from_model2(ai_data, dish_type, variant):
    try:
        # print(ai_data)
        total_nutrients = {}
        output_ingredients = []
        ingredient_distributed_nutrients = {}
        logger.info("Processing ingredients list...")

        if dish_type == "normal":
            if variant == "full":
                print("here we are in normal full")
                ingredients_list = ai_data.get("dish_variants", {}).get("normal", {}).get("full", {}).get("ingredients", [])
                # ingredients_list = ai_data
                print(f"ingredients_list: {ingredients_list}")

                # Ensure ingredients_list is a list, if for some reason it's not (e.g., if it's None or a different type)
                if not isinstance(ingredients_list, list):
                    ingredients_list = []

                for item in ingredients_list:
                    ingredient_name = item['name'] 
                    quantity = float(item['quantity']) 
                    unit = item['unit']  
                    print(f"{ingredient_name},{ingredient_name}")

                    try:
                        # Handle "to taste" or similar non-numeric quantities
                        if quantity == "to taste":
                            logging.warning(f"Quantity 'to taste' detected. Setting default value: 5g.")
                            quantity = "5"
                            unit = "g"

                        # Convert quantity to float for further processing
                        quantity = float(quantity)
                        logging.debug(f"Converted quantity: {quantity}, Unit: {unit}")

                    except ValueError as e:
                        logging.error(f"Error converting quantity '{quantity}' to float: {e}")
                        # Handle error or fallback logic
                        quantity = 5.0  # Default to 5g
                        unit = "g"
                    
                    logging.debug(f"Processing ingredient: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")
                    print("check aboveeeeeeeeeeeeeeee")
                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g.")
                            output_ingredients.append(item)
                        else:
                            logging.warning(f"Could not convert {ingredient_name} from ml to g. Keeping original unit.")
                            output_ingredients.append(item)
                    else:
                        logging.info(f"No conversion needed for {ingredient_name}. Adding as is.")
                        output_ingredients.append(item)

#      #******************************pooja********************************#
                logging.info("Checking for allergens in the ingredients...")

                allergic_content = []  # Directly store allergy categories here

                for item in ingredients_list:
                    ingredient_name = item["name"]
                    ingredient_allergy_categories = get_allergy_categories(ingredient_name)

                    # Add allergy categories directly to allergic_content
                    allergic_content.extend(ingredient_allergy_categories)

                # Remove duplicates (if any) by converting to a set
                allergic_content = list(set(allergic_content))

                # *Step 2: Store allergen information in ai_data*
                ai_data["allergic_content"] = allergic_content  # Directly store categories

                logging.info(f"Allergic content added to ai_data: {allergic_content}")

                
                # Step 3: Update the database with allergic content
                # try:
                #     db["RestaurantMenuData"].update_one(
                #         {"$set": {"allergic_content": ai_data["allergic_content"]}}
                #     )
                #     logging.info(f"Allergic content successfully updated in the database for dish: {ai_data['_id']}")
                # except Exception as e:
                #     logging.error(f"Failed to update allergic content in the database: {e}", exc_info=True)
                # Step 3: Update the database with allergic content
                
                try:
                    filter = {"allergic_content": ai_data["allergic_content"]}  # Assuming ai_data contains the document ID
                    update = {
                        "$set": {
                            "allergic_content": ai_data["allergic_content"]
                        }
                    }
                    
                    db["RestaurantMenuData"].update_one(filter, update)
                    logging.info(f"Allergic content successfully updated in the database for dish: {ai_data['allergic_content']}")
                except Exception as e:
                    logging.error(f"Failed to update allergic content in the database: {e}", exc_info=True)

                # Nutrient calculation
                for item in output_ingredients:
                    ingredient_name = item["name"]
                    quantity = float(item["quantity"])
                    unit = item["unit"]

                    logging.debug(f"Calculating nutrients for: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")

                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams for nutrient calculation.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g for nutrient calculation.")
                            quantity = quantity_g
                            unit = "g"

                    if unit == "g":
                        logging.debug(f"Fetching nutrient data for {ingredient_name} with quantity {quantity} g.")
                        ingredient_nutrients = calculate_nutrients(ingredient_name, quantity, ingredient_retriever)
                        if ingredient_nutrients:
                            logging.info(f"Nutrients for {ingredient_name}: {ingredient_nutrients}")
                            for nutrient, value in ingredient_nutrients.items():
                                if nutrient in total_nutrients:
                                    total_nutrients[nutrient] = round(total_nutrients[nutrient] + value, 2)
                                    logging.debug(f"Updated total {nutrient}: {total_nutrients[nutrient]}")
                                else:
                                    total_nutrients[nutrient] = value
                                    logging.debug(f"Added {nutrient}: {value} to total nutrients.")
                        else:
                            logging.warning(f"No nutrient data found for {ingredient_name}.")


                # Extract cooking time and temperature
                # logging.debug(f"Extracting cooking time and temperature from ai_data: {ai_data}")
                # print(f"check here:{ai_data}")
                # cooking_time = int(re.search(r'\d+', ai_data['cooking_time']).group())
                # cooking_temperature = int(re.search(r'\d+', ai_data['cooking_temperature']).group())

                # Extract cooking time and temperature
                logging.debug(f"Extracting cooking time and temperature from ai_data: {ai_data}")
                try:
                    cooking_time = int(re.search(r'\d+', ai_data['cooking_time']).group())
                except:
                    cooking_time = "10"

                try:
                    cooking_temperature = int(re.search(r'\d+', ai_data['cooking_temperature']).group())    
                except:
                    cooking_temperature = "20"

                logging.info(f"Cooking time extracted: {cooking_time} minutes")
                logging.info(f"Cooking temperature extracted: {cooking_temperature}°C")

                # Store original nutrient values for comparison
                original_nutrients_values = total_nutrients
                logging.debug(f"Original nutrients before cooking retention: {original_nutrients_values}")

                cooking_method = ai_data.get("cooking_method", ["None"])
                if not cooking_method:  
                    cooking_method = ["None"]

                if ai_data:
                    total_nutrients = apply_cooking_retention(
                        total_nutrients,
                        cooking_method[0],
                        cooking_time,
                        cooking_temperature
                    )
                    logging.info(f"Total nutrients after applying cooking retention: {total_nutrients}")


                # Convert `total_nutrients` dictionary into a list of dictionaries
                total_nutrients_list = [
                    {"name": nutrient.upper(), "quantity": round(value, 2), "unit": nutrient_units.get(nutrient, "")}
                    for nutrient, value in total_nutrients.items()
                ]
                logging.debug(f"Total nutrients converted to list: {total_nutrients_list}")

                # Distribute nutrients among ingredients
                ingredient_distributed_nutrients = distribute_nutrients(total_nutrients)
                logging.info(f"Distributed nutrients across ingredients: {ingredient_distributed_nutrients}")

                # Prepare model2 data
                model2_data = {
                    "ingredients": output_ingredients,
                    "nutrients": total_nutrients_list,
                    "calculate_nutrients": ingredient_distributed_nutrients,
                }
                logging.debug(f"Model2 data prepared: {model2_data}")

                # Update ai_data with model2 data
                ai_data["dish_variants"]["normal"]["full"].update(model2_data)
                logging.info(f"Updated ai_data with model2 data: {model2_data}")

                # Log final output for debugging
                logging.debug(f"Output ingredients: {output_ingredients}")
                logging.info(f"Final total_nutrients_list calculated: {total_nutrients_list}")
                logging.info(f"Final ingredient_distributed_nutrients calculated: {ingredient_distributed_nutrients}")
                        
                # save_json_to_file(total_nutrients_list, "dishes_output", "full_normal_total.json" )
                # save_json_to_file(ingredient_distributed_nutrients, "dishes_output", "full_normal_ing_dis.json" )

            else:
                ingredients_list = ai_data.get("dish_variants", {}).get("normal", {}).get("half", {}).get("ingredients", [])
                # ingredients_list = ai_data

                # Ensure ingredients_list is a list, if for some reason it's not (e.g., if it's None or a different type)
                if not isinstance(ingredients_list, list):
                    ingredients_list = []

                for item in ingredients_list:
                    ingredient_name = item['name'] 
                    quantity = float(item['quantity']) 
                    unit = item['unit']  

                    try:
                        # Handle "to taste" or similar non-numeric quantities
                        if quantity == "to taste":
                            logging.warning(f"Quantity 'to taste' detected. Setting default value: 5g.")
                            quantity = "5"
                            unit = "g"

                        # Convert quantity to float for further processing
                        quantity = float(quantity)
                        logging.debug(f"Converted quantity: {quantity}, Unit: {unit}")

                    except ValueError as e:
                        logging.error(f"Error converting quantity '{quantity}' to float: {e}")
                        # Handle error or fallback logic
                        quantity = 5.0  # Default to 5g
                        unit = "g"
                    
                    logging.debug(f"Processing ingredient: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")
                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g.")
                            output_ingredients.append(item)
                        else:
                            logging.warning(f"Could not convert {ingredient_name} from ml to g. Keeping original unit.")
                            output_ingredients.append(item)
                    else:
                        logging.info(f"No conversion needed for {ingredient_name}. Adding as is.")
                        output_ingredients.append(item)

             #**********************pooja******************************#                 
                logging.info("Checking for allergens in the ingredients...")

                allergic_content = []  # Directly store allergy categories here

                for item in ingredients_list:
                    ingredient_name = item["name"]
                    ingredient_allergy_categories = get_allergy_categories(ingredient_name)

                    # Add allergy categories directly to allergic_content
                    allergic_content.extend(ingredient_allergy_categories)

                # Remove duplicates (if any) by converting to a set
                allergic_content = list(set(allergic_content))

                # *Step 2: Store allergen information in ai_data*
                ai_data["allergic_content"] = allergic_content  # Directly store categories

                logging.info(f"Allergic content added to ai_data: {allergic_content}")

                
                # Step 3: Update the database with allergic content
                try:
                    db["RestaurantMenuData"].update_one(
                        {"$set": {"allergic_content": ai_data["allergic_content"]}}
                    )
                    logging.info(f"Allergic content successfully updated in the database for dish: {ai_data['_id']}")
                except Exception as e:
                    logging.error(f"Failed to update allergic content in the database: {e}", exc_info=True)


                # Nutrient calculation
                for item in output_ingredients:
                    ingredient_name = item["name"]
                    quantity = float(item["quantity"])
                    unit = item["unit"]

                    logging.debug(f"Calculating nutrients for: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")

                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams for nutrient calculation.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g for nutrient calculation.")
                            quantity = quantity_g
                            unit = "g"

                    if unit == "g":
                        logging.debug(f"Fetching nutrient data for {ingredient_name} with quantity {quantity} g.")
                        ingredient_nutrients = calculate_nutrients(ingredient_name, quantity, ingredient_retriever)
                        if ingredient_nutrients:
                            logging.info(f"Nutrients for {ingredient_name}: {ingredient_nutrients}")
                            for nutrient, value in ingredient_nutrients.items():
                                if nutrient in total_nutrients:
                                    total_nutrients[nutrient] = round(total_nutrients[nutrient] + value, 2)
                                    logging.debug(f"Updated total {nutrient}: {total_nutrients[nutrient]}")
                                else:
                                    total_nutrients[nutrient] = value
                                    logging.debug(f"Added {nutrient}: {value} to total nutrients.")
                        else:
                            logging.warning(f"No nutrient data found for {ingredient_name}.")


                # Extract cooking time and temperature
                logging.debug(f"Extracting cooking time and temperature from ai_data: {ai_data}")
                cooking_time = int(re.search(r'\d+', ai_data['cooking_time']).group())
                cooking_temperature = int(re.search(r'\d+', ai_data['cooking_temperature']).group())
                logging.info(f"Cooking time extracted: {cooking_time} minutes")
                logging.info(f"Cooking temperature extracted: {cooking_temperature}°C")

                # Store original nutrient values for comparison
                original_nutrients_values = total_nutrients
                logging.debug(f"Original nutrients before cooking retention: {original_nutrients_values}")

                cooking_method = ai_data.get("cooking_method", ["None"])
                if not cooking_method:  
                    cooking_method = ["None"]
                    
                if ai_data:
                    total_nutrients = apply_cooking_retention(
                        total_nutrients,
                        cooking_method[0],
                        cooking_time,
                        cooking_temperature
                    )
                    logging.info(f"Total nutrients after applying cooking retention: {total_nutrients}")

                # Convert `total_nutrients` dictionary into a list of dictionaries
                total_nutrients_list = [
                    {"name": nutrient.upper(), "quantity": round(value, 2), "unit": nutrient_units.get(nutrient, "")}
                    for nutrient, value in total_nutrients.items()
                ]
                logging.debug(f"Total nutrients converted to list: {total_nutrients_list}")

                # Distribute nutrients among ingredients
                ingredient_distributed_nutrients = distribute_nutrients(total_nutrients)
                logging.info(f"Distributed nutrients across ingredients: {ingredient_distributed_nutrients}")
                
                # Prepare model2 data
                model2_data = {
                    "ingredients": output_ingredients,
                    "nutrients": total_nutrients_list,
                    "calculate_nutrients": ingredient_distributed_nutrients,
                }
                logging.debug(f"Model2 data prepared: {model2_data}")

                # Update ai_data with model2 data
                if "normal" not in ai_data["dish_variants"]:
                    ai_data["dish_variants"]["normal"] = {} 

                if "half" not in ai_data["dish_variants"]["normal"]:
                    ai_data["dish_variants"]["normal"]["half"] = {}                

                ai_data["dish_variants"]["normal"]["half"].update(model2_data)
                logging.info(f"Updated ai_data with model2 data: {model2_data}")

                # Log final output for debugging
                logging.debug(f"Output ingredients: {output_ingredients}")
                logging.info(f"Final total_nutrients_list calculated: {total_nutrients_list}")
                logging.info(f"Final ingredient_distributed_nutrients calculated: {ingredient_distributed_nutrients}")

        elif dish_type == "jain":
            if variant == "full":
                ingredients_list = ai_data.get("dish_variants", {}).get("jain", {}).get("full", {}).get("ingredients", [])
                # ingredients_list = ai_data

                # Ensure ingredients_list is a list, if for some reason it's not (e.g., if it's None or a different type)
                if not isinstance(ingredients_list, list):
                    ingredients_list = []

                for item in ingredients_list:
                    ingredient_name = item['name'] 
                    quantity = float(item['quantity']) 
                    unit = item['unit']  
                    # print(f"{ingredient_name},{ingredient_name}")

                    try:
                        # Handle "to taste" or similar non-numeric quantities
                        if quantity == "to taste":
                            logging.warning(f"Quantity 'to taste' detected. Setting default value: 5g.")
                            quantity = "5"
                            unit = "g"

                        # Convert quantity to float for further processing
                        quantity = float(quantity)
                        logging.debug(f"Converted quantity: {quantity}, Unit: {unit}")

                    except ValueError as e:
                        logging.error(f"Error converting quantity '{quantity}' to float: {e}")
                        # Handle error or fallback logic
                        quantity = 5.0  # Default to 5g
                        unit = "g"
                    
                    logging.debug(f"Processing ingredient: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")
                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g.")
                            output_ingredients.append(item)
                        else:
                            logging.warning(f"Could not convert {ingredient_name} from ml to g. Keeping original unit.")
                            output_ingredients.append(item)
                    else:
                        logging.info(f"No conversion needed for {ingredient_name}. Adding as is.")
                        output_ingredients.append(item)

                # Nutrient calculation
                for item in output_ingredients:
                    ingredient_name = item["name"]
                    quantity = float(item["quantity"])
                    unit = item["unit"]

                    logging.debug(f"Calculating nutrients for: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")

                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams for nutrient calculation.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g for nutrient calculation.")
                            quantity = quantity_g
                            unit = "g"

                    if unit == "g":
                        logging.debug(f"Fetching nutrient data for {ingredient_name} with quantity {quantity} g.")
                        ingredient_nutrients = calculate_nutrients(ingredient_name, quantity, ingredient_retriever)
                        if ingredient_nutrients:
                            logging.info(f"Nutrients for {ingredient_name}: {ingredient_nutrients}")
                            for nutrient, value in ingredient_nutrients.items():
                                if nutrient in total_nutrients:
                                    total_nutrients[nutrient] = round(total_nutrients[nutrient] + value, 2)
                                    logging.debug(f"Updated total {nutrient}: {total_nutrients[nutrient]}")
                                else:
                                    total_nutrients[nutrient] = value
                                    logging.debug(f"Added {nutrient}: {value} to total nutrients.")
                        else:
                            logging.warning(f"No nutrient data found for {ingredient_name}.")


                # Extract cooking time and temperature
                logging.debug(f"Extracting cooking time and temperature from ai_data: {ai_data}")
                cooking_time = int(re.search(r'\d+', ai_data['cooking_time']).group())
                cooking_temperature = int(re.search(r'\d+', ai_data['cooking_temperature']).group())
                logging.info(f"Cooking time extracted: {cooking_time} minutes")
                logging.info(f"Cooking temperature extracted: {cooking_temperature}°C")

                # Store original nutrient values for comparison
                original_nutrients_values = total_nutrients
                logging.debug(f"Original nutrients before cooking retention: {original_nutrients_values}")

                cooking_method = ai_data.get("cooking_method", ["None"])
                if not cooking_method:  
                    cooking_method = ["None"]
                    
                if ai_data:
                    total_nutrients = apply_cooking_retention(
                        total_nutrients,
                        cooking_method[0],
                        cooking_time,
                        cooking_temperature
                    )
                    logging.info(f"Total nutrients after applying cooking retention: {total_nutrients}")

                # Convert `total_nutrients` dictionary into a list of dictionaries
                total_nutrients_list = [
                    {"name": nutrient.upper(), "quantity": round(value, 2), "unit": nutrient_units.get(nutrient, "")}
                    for nutrient, value in total_nutrients.items()
                ]
                logging.debug(f"Total nutrients converted to list: {total_nutrients_list}")

                # Distribute nutrients among ingredients
                ingredient_distributed_nutrients = distribute_nutrients(total_nutrients)
                logging.info(f"Distributed nutrients across ingredients: {ingredient_distributed_nutrients}")

                # Prepare model2 data
                model2_data = {
                    "ingredients": output_ingredients,
                    "nutrients": total_nutrients_list,
                    "calculate_nutrients": ingredient_distributed_nutrients,
                }
                logging.debug(f"Model2 data prepared: {model2_data}")

                # Update ai_data with model2 data
                ai_data["dish_variants"]["jain"]["full"].update(model2_data)
                logging.info(f"Updated ai_data with model2 data: {model2_data}")

                # Log final output for debugging
                logging.debug(f"Output ingredients: {output_ingredients}")
                logging.info(f"Final total_nutrients_list calculated: {total_nutrients_list}")
                logging.info(f"Final ingredient_distributed_nutrients calculated: {ingredient_distributed_nutrients}")

            else:
                ingredients_list = ai_data.get("dish_variants", {}).get("jain", {}).get("half", {}).get("ingredients", [])
                # ingredients_list = ai_data

                # Ensure ingredients_list is a list, if for some reason it's not (e.g., if it's None or a different type)
                if not isinstance(ingredients_list, list):
                    ingredients_list = []

                for item in ingredients_list:
                    ingredient_name = item['name'] 
                    quantity = float(item['quantity']) 
                    unit = item['unit']  
                    # print(f"{ingredient_name},{ingredient_name}")

                    try:
                        # Handle "to taste" or similar non-numeric quantities
                        if quantity == "to taste":
                            logging.warning(f"Quantity 'to taste' detected. Setting default value: 5g.")
                            quantity = "5"
                            unit = "g"

                        # Convert quantity to float for further processing
                        quantity = float(quantity)
                        logging.debug(f"Converted quantity: {quantity}, Unit: {unit}")

                    except ValueError as e:
                        logging.error(f"Error converting quantity '{quantity}' to float: {e}")
                        # Handle error or fallback logic
                        quantity = 5.0  # Default to 5g
                        unit = "g"
                    
                    logging.debug(f"Processing ingredient: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")
                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g.")
                            output_ingredients.append(item)
                        else:
                            logging.warning(f"Could not convert {ingredient_name} from ml to g. Keeping original unit.")
                            output_ingredients.append(item)
                    else:
                        logging.info(f"No conversion needed for {ingredient_name}. Adding as is.")
                        output_ingredients.append(item)

                # Nutrient calculation
                for item in output_ingredients:
                    ingredient_name = item["name"]
                    quantity = float(item["quantity"])
                    unit = item["unit"]

                    logging.debug(f"Calculating nutrients for: {ingredient_name}, Quantity: {quantity}, Unit: {unit}")

                    if unit == "ml":
                        logging.debug(f"Converting {quantity} ml of {ingredient_name} to grams for nutrient calculation.")
                        quantity_g = convert_ml_to_g(ingredient_name, quantity, unit_retriever)
                        if quantity_g:
                            logging.info(f"Converted {quantity} ml of {ingredient_name} to {quantity_g} g for nutrient calculation.")
                            quantity = quantity_g
                            unit = "g"

                    if unit == "g":
                        logging.debug(f"Fetching nutrient data for {ingredient_name} with quantity {quantity} g.")
                        ingredient_nutrients = calculate_nutrients(ingredient_name, quantity, ingredient_retriever)
                        if ingredient_nutrients:
                            logging.info(f"Nutrients for {ingredient_name}: {ingredient_nutrients}")
                            for nutrient, value in ingredient_nutrients.items():
                                if nutrient in total_nutrients:
                                    total_nutrients[nutrient] = round(total_nutrients[nutrient] + value, 2)
                                    logging.debug(f"Updated total {nutrient}: {total_nutrients[nutrient]}")
                                else:
                                    total_nutrients[nutrient] = value
                                    logging.debug(f"Added {nutrient}: {value} to total nutrients.")
                        else:
                            logging.warning(f"No nutrient data found for {ingredient_name}.")


                # Extract cooking time and temperature
                logging.debug(f"Extracting cooking time and temperature from ai_data: {ai_data}")
                cooking_time = int(re.search(r'\d+', ai_data['cooking_time']).group())
                cooking_temperature = int(re.search(r'\d+', ai_data['cooking_temperature']).group())
                logging.info(f"Cooking time extracted: {cooking_time} minutes")
                logging.info(f"Cooking temperature extracted: {cooking_temperature}°C")

                # Store original nutrient values for comparison
                original_nutrients_values = total_nutrients
                logging.debug(f"Original nutrients before cooking retention: {original_nutrients_values}")

                # Apply cooking retention if `ai_data` is valid
                cooking_method = ai_data.get("cooking_method", ["None"])
                if not cooking_method:  
                    cooking_method = ["None"]
                    
                if ai_data:
                    total_nutrients = apply_cooking_retention(
                        total_nutrients,
                        cooking_method[0],
                        cooking_time,
                        cooking_temperature
                    )
                    logging.info(f"Total nutrients after applying cooking retention: {total_nutrients}")

                # Convert `total_nutrients` dictionary into a list of dictionaries
                total_nutrients_list = [
                    {"name": nutrient.upper(), "quantity": round(value, 2), "unit": nutrient_units.get(nutrient, "")}
                    for nutrient, value in total_nutrients.items()
                ]
                logging.debug(f"Total nutrients converted to list: {total_nutrients_list}")

                # Distribute nutrients among ingredients
                ingredient_distributed_nutrients = distribute_nutrients(total_nutrients)
                logging.info(f"Distributed nutrients across ingredients: {ingredient_distributed_nutrients}")

                # Prepare model2 data
                model2_data = {
                    "ingredients": output_ingredients,
                    "nutrients": total_nutrients_list,
                    "calculate_nutrients": ingredient_distributed_nutrients,
                }
                logging.debug(f"Model2 data prepared: {model2_data}")

                # Ensure the "half" variant exists before updating it
                if "half" not in ai_data["dish_variants"]["jain"]:
                    ai_data["dish_variants"]["jain"]["half"] = {}
                    
                # Update ai_data with model2 data
                ai_data["dish_variants"]["jain"]["half"].update(model2_data)
                logging.info(f"Updated ai_data with model2 data: {model2_data}")

                # Log final output for debugging
                logging.debug(f"Output ingredients: {output_ingredients}")
                logging.info(f"Final total_nutrients_list calculated: {total_nutrients_list}")
                logging.info(f"Final ingredient_distributed_nutrients calculated: {ingredient_distributed_nutrients}")
        else:
            print("correct nutrient function")
        return total_nutrients_list, ingredient_distributed_nutrients

    except Exception as e:
        logging.error(f"Error processing ingredients: {str(e)}", exc_info=True)
        return [], []
    

    
