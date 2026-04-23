import logging
import os
import random
import time
import google.generativeai as genai
import json
import copy


from fitshield_webapp.AI.AIModel.ai_image_model import generate_img
from fitshield_webapp.AI.AIModel.ai_model2 import process_ingredients_nutrients_from_model2
from rest_framework import status
from rest_framework.response import Response

from fitshield_webapp.AI.AIModel.ai_model3 import adjust_quantities_with_min_max, get_prior_ingredients_from_model3
from fitshield_webapp.AI.AIModel.model_helpers.remove_swap_items import remove_swapped_item_essential_category
from fitshield_webapp.utils.generate_id import generate_dish_id, generate_ingredient_id
import nltk

nltk.download('punkt_tab')
from .model_helpers.ingredients_swaps import swaps

import logging
logging.basicConfig(
    level=logging.DEBUG,  
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# Model 1
genai.configure(api_key="AIzaSyC7PuTD0r_KKmKwqcnqpZTeA0-84bOSj24")

def upload_to_gemini(path, mime_type=None):
  file = genai.upload_file(path, mime_type=mime_type)
  # print(f"Uploaded file '{file.display_name}' as: {file.uri}")
  return file

def wait_for_files_active(files):

  for name in (file.name for file in files):
    file = genai.get_file(name)
    while file.state.name == "PROCESSING":
      print(".", end="", flush=True)
      time.sleep(10)
      file = genai.get_file(name)
    if file.state.name != "ACTIVE":
      raise Exception(f"File {file.name} failed to process")



generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

model = genai.GenerativeModel(
  model_name="gemini-1.5-flash",
  generation_config=generation_config,
  system_instruction="Generate a JSON object for a dish based on the following inputs:\n1.\tdish_name: Name of the dish.\n2.\tfood_category: Specifies whether the dish is Vegetarian or Non-vegetarian.\nThe JSON object should include:\n{\n  \"dish_name\": \"__\",\n  \"dish_description\": \"__\",\n  \"cuisine_category\": {\n    \"continental_region\": \"__\",\n    \"specific_cuisine\": \"__\",\n    \"subcategory\": \"__\"\n  },\n  \"timing_category\": [\n    \"__\"\n  ],\n  \"meal_category\": [\n    \"__\"\n  ],\n  \"food_category\": \"__\",\n  \"cooking_method\": [\n    \"__\"\n  ],\n  \"cooking_time\": \"__\",\n  \"cooking_temperature\": \"__\",\n  \"ingredients\": [\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    },\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    },\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    }\n  ],\n  \"allergic_content\": {},\n  \"serving\": {\n    \"size\": \"__\",\n    \"unit\": \"__\"\n  },\n  \"cooking_steps\": [\n    \"__\",\n    \"__\",\n    \"__\"\n  ]\n  \"complementary_dishes\": [\n    \"__\",\n    \"__\",\n    \"__\"\n  ],\n  \"nutritional_values_of_dish\":{\n    \"energy\": __,\n    \"carbs\": __,\n    \"proteins\": __,\n    \"fats\": __,\n    \"fibers\": __,\n    \"thiamin\": __,\n    \"riboflavin\": __,\n    \"niacin\": __,\n    \"vitamin_b5\": __,\n    \"vitamin_b6\": __,\n    \"vitamin_c\": __,\n    \"biotin\": __,\n    \"folate\": __,\n    \"vitamin_a\": __,\n    \"vitamin_d2\": __,\n    \"vitamin_d3\": __,\n    \"vitamin_k1\": __,\n    \"vitamin_k2\": __,\n    \"carotenoids\": __,\n    \"vitamin_e\": __,\n    \"calcium\": __,\n    \"copper\": __,\n    \"iron\": __,\n    \"magnesium\": __,\n    \"manganese\": __,\n    \"potassium\": __,\n    \"sodium\": __,\n    \"zinc\": __,\n    \"cholesterol\": __,\n    \"sugar\": __,\n    \"sodium\": __,\n    \"zinc\": __,\n  }\n}\n\nIngredient Database:\n\nNote: You must reference a pre-existing text file containing ingredient names whenever generating the dish's ingredients list. The ingredient names in this file should be considered valid, and you must use those exact names for all ingredients.",
)

# files = [
#   upload_to_gemini("D:\\Fitshield\\fitshield\\fitshield_webapp\\AI\\AIModel\\food_names.txt", mime_type="text/plain"),
# ]

# Get the dynamic path to the file based on the current working directory
def get_file_path(filename):
    # Get the current working directory (where the script is running)
    base_dir = os.path.dirname(os.path.abspath(__file__))  # To get the current script's directory
    
    # Dynamically create the path to the file in the AIModel directory
    # print(f"base_dir: {base_dir}")
    file_path = os.path.join(base_dir, filename)
    
    # Check if the file exists before uploading
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    return file_path

# Example usage: getting the dynamic file path for food_names.txt
filename = "food_names.txt"
file_path = get_file_path(filename)

# Now use the file path to upload
files = [
    upload_to_gemini(file_path, mime_type="text/plain")
]

# Some files have a processing delay. Wait for them to be ready.
wait_for_files_active(files)
chat_session = model.start_chat(
  history=[
    {
      "role": "user",
      "parts": [
        files[0],
      ],
    },
    {
      "role": "model",
      "parts": [
        "```json\n{\n  \"dish_name\": \"Spicy Peanut Noodles with Chicken\",\n  \"dish_description\": \"A flavorful and spicy noodle dish with tender chicken, crunchy vegetables, and a creamy peanut sauce.\",\n  \"cuisine_category\": {\n    \"continental_region\": \"Asian\",\n    \"specific_cuisine\": \"Thai\",\n    \"subcategory\": \"Noodles\"\n  },\n  \"timing_category\": [\n    \"Lunch\",\n    \"Dinner\"\n  ],\n  \"meal_category\": [\n    \"Main Course\"\n  ],\n  \"food_category\": \"Non-vegetarian\",\n  \"cooking_method\": [\n    \"Stir-frying\",\n    \"Boiling\"\n  ],\n  \"cooking_time\": \"30 minutes\",\n  \"cooking_temperature\": \"Medium-high heat\",\n  \"ingredients\": [\n    {\n      \"name\": \"Chicken, poultry, breast, skinless\",\n      \"quantity\": \"200\",\n      \"unit\": \"grams\",\n      \"description\": \"Cubed chicken breast\"\n    },\n    {\n      \"name\": \"Noodles with vegetables in tomato-based sauce, diet frozen meal\",\n      \"quantity\": \"200\",\n      \"unit\": \"grams\",\n      \"description\": \"Cooked according to package directions\"\n    },\n    {\n      \"name\": \"Peanut butter\",\n      \"quantity\": \"4\",\n      \"unit\": \"tablespoons\",\n      \"description\": \"Smooth peanut butter\"\n    },\n    {\n      \"name\": \"Soy sauce\",\n      \"quantity\": \"20\",\n      \"unit\": \"ml\",\n      \"description\": \"Regular soy sauce\"\n    },\n    {\n      \"name\": \"Chillies, green\",\n      \"quantity\": \"5\",\n      \"unit\": \"g\",\n      \"description\": \"Finely chopped green chillies\"\n    },\n     {\n      \"name\": \"Garlic, big clove\",\n      \"quantity\": \"5\",\n      \"unit\": \"g\",\n      \"description\": \"Minced garlic\"\n    },\n    {\n      \"name\": \"Ginger, fresh\",\n      \"quantity\": \"3\",\n      \"unit\": \"ml\",\n      \"description\": \"Grated fresh ginger\"\n    },\n    {\n      \"name\": \"Capsicum, red\",\n      \"quantity\": \"5\",\n      \"unit\": \"g\",\n      \"description\": \"Sliced red bell pepper\"\n    },\n    {\n      \"name\": \"Onions, big\",\n      \"quantity\": \"10\",\n      \"unit\": \"g\",\n      \"description\": \"Sliced onions\"\n    },\n    {\n      \"name\": \"Water\",\n      \"quantity\": \"30\",\n      \"unit\": \"ml\",\n      \"description\": \"To adjust sauce consistency\"\n    },\n    {\n      \"name\": \"Sesame oil\",\n      \"quantity\": \"5\",\n      \"unit\": \"ml\",\n      \"description\": \"For added flavor\"\n    }\n  ],\n  \"allergic_content\": {\n    \"peanuts\": true,\n    \"soy\": true,\n    \"chillies\": true\n  },\n  \"serving\": {\n    \"size\": \"1\",\n    \"unit\": \"serving\"\n  },\n  \"cooking_steps\": [\n    \"Cook noodles according to package directions.\",\n    \"Stir-fry chicken in sesame oil until cooked through.\",\n    \"In a separate bowl, whisk together peanut butter, soy sauce, green chillies, garlic, and ginger. Add water to thin if needed.\",\n    \"Combine cooked noodles, chicken, and peanut sauce. Stir well to coat.\",\n    \"Serve hot and garnish with chopped red bell pepper and onions.\"\n  ],\n  \"complementary_dishes\": [\n    \"Steamed rice\",\n    \"Spring rolls\",\n    \"Vegetable stir-fry\"\n  ],\n  \"nutritional_values_of_dish\": {\n    \"energy\": 500,\n    \"carbs\": 50,\n    \"proteins\": 30,\n    \"fats\": 25,\n    \"fibers\": 5,\n    \"thiamin\": 0.5,\n    \"riboflavin\": 0.6,\n    \"niacin\": 5,\n    \"vitamin_b5\": 2,\n    \"vitamin_b6\": 1,\n    \"vitamin_c\": 10,\n    \"biotin\": 5,\n    \"folate\": 200,\n    \"vitamin_a\": 1000,\n    \"vitamin_d2\": 0,\n    \"vitamin_d3\": 0,\n    \"vitamin_k1\": 10,\n    \"vitamin_k2\": 0,\n    \"carotenoids\": 1000,\n    \"vitamin_e\": 5,\n    \"calcium\": 100,\n    \"copper\": 0.5,\n    \"iron\": 5,\n    \"magnesium\": 100,\n    \"manganese\": 1,\n    \"potassium\": 500,\n    \"sodium\": 600,\n    \"zinc\": 5\n  }\n}\n```\n",
      ],
    },
    {
      "role": "user",
      "parts": [
        "You are a highly skilled culinary expert and food data analyst specializing in generating detailed dish information in JSON format. Your expertise includes correcting dish names (regardless of language or spelling variations) and presenting comprehensive details such as description, ingredients, cooking steps, and dietary information.\nInput Details:\n1.\tdish_name: Correct any spelling errors and identify the dish name, regardless of language.\n2.\tfood_category: Specifies whether the dish is Vegetarian or Non-vegetarian. \n                                    If eggs are included as an ingredient, classify the dish as non-vegetarian.\nJSON Output Requirements:\n1.\tdish_name: Corrected name of the dish.\n2.\tdish_description: If provided, use this description directly to extract and must include all ingredients and cooking methods. Otherwise, A description to be generated between 20 to 200 characters highlighting main ingredients, flavor profile, and preparation style. Avoid excessive special characters.\n3.\tcuisine_category:\no\tcontinental_region: Validate against predefined regions (e.g., Asia, Europe, North America).\no\tspecific_cuisine: Match predefined cuisines within the selected region.\no\tsubcategory: Validate subcategories under the cuisine (e.g., \"North Indian\" for Indian cuisine).\n4.\ttiming_category: Select applicable options:\no\tBreakfast, Lunch, Snack, Dinner, Brunch, Midnight Snack\no\tUse: \"timing_category\": [\"__\"] for a single category or multiple options.\n5.\tmeal_category: Must select one options from these but should be in list:\no\tStarter, Soup, Salad, Main Course, Side Dish, Dessert, Drink, Snack\n6.\tcooking_method: If the description includes cooking methods, extract the primary method from it.\nIf the description does not include methods, extract them from the provided cooking steps.\nIf both are unavailable or inconclusive, infer a generic cooking method using an LLM. But you have to choose one or more methods from below list:\no\tBoiling, Steaming, Microwaving, Baking, Grilling, Frying, Sautéing, Pressure Cooking, Slow Cooking\n7.\tcooking_time: Provide time in standard format (e.g., \"45 minutes\") and time must be in minutes.\n8.\tcooking_temperature: Provide in °C or °F, ensuring values are within valid ranges (e.g., 50°C–500°C). Convert Fahrenheit to Celsius if necessary. It must be in °C, for example 20 °C.\n9.\tingredients: You must have to take name of ingredients food_names.txt. A detailed list of ingredients including:\no\tname: Standardized English name.  \no\tquantity: Needed as per dish but it must be in number.\no\tunit: g (grams) or ml (milliliters), and There must not be in any other units if there is in then convert it into g (grams) or ml (milliliters) from non metrics too. If unit is in pieces the convert into exact gm or ml with respect to corresponding package. If any dish contains bread or pav or bun include it in ingredients and take it's unit as grams \"g\". Make sure not to use pieces, number , nos etc. in any of the ingredients use grams \"g\" for all solid ingredients and for liquid ingredients use \"ml\" and make sure for salt and pepper too you take it in grams \"g\".\no\tWhen including eggs as an ingredient, ensure the quantity is provided in grams. Assume that one egg weighs 40 grams, and if the quantity is given in pieces, multiply the number of pieces by 40 to convert it into grams.\no\tdescription: Ingredient state (e.g., \"chopped,\" \"boiled\").\nExample:\n{\n\"name\": \"Rice\",\n\"quantity\": \"50\",\n\"unit\": \"g\",\n\"description\": \"chopped\"\n}\n10.\tallergic_content: Leave this field empty. \n11.\tserving: Calculate serving size based on ingredient quantities. Consolidate into grams or milliliters. Example:\n{\n  \"size\": \" \",\n  \"unit\": \"g\"\n}\n12.\tcooking_steps: Provide detailed, step-by-step cooking instructions. Example:\n[\n  \"1. Rinse rice and moong dal thoroughly.\",\n  \"2. Combine rice and dal with water in a pan and bring to a boil.\",\n  \"3. Heat ghee in another pan and sauté spices.\",\n  \"4. Mix the spice mixture into the cooked khichdi and stir well.\"\n]\n13. complementary_dishes : Find out complementary dishes from \"dish_description\" or \"dish_name\". I want complementary dishes in list format.\nConsider this as the End of Input and Now all the things will be considered as Final output.(FO)\n\n\nKey Notes:\n•\tEnsure the dish details are tailored to the inputs (dish_name and food_category).\n•\tValidate all inputs and ensure accuracy in the generated JSON.\n•\tI only want json object in response nothing else.\n•\tI only want \"unit\" in g or ml in ingredients.\n•      In cooking_temperature says Room temperature but it must compulsory show number related to cooking temperature in Celsius. \n•      Ingredient names must be pulled directly from the provided ingredient database text file.\n•      Use oil is required use vegetable oil by default. \n•      Must generate \"nutritional_values_of_dish\" values.\n•      In ingredients units must be \"g\" or \"ml\". it should not be empty string. And ingredients must not be repeated.\n\n14. nutritional_values_of_dish : You consider your self as an expert nutrition value deriver. Provide details of below list nutrient details with specified units (in case you didn't find unit exact match- You have to convert those figures with accordance of standard convertor but the final output must be in given units only )\nFor calculating the nutrients values Strictly consider 200gm as serving sizes.\nYou have to consider Final output (FO) as the input for this calculation and perform the calculation with consideration of Cooking style , Temperature and other factors you may include. \nThe raw food database must be used from USDA database, Nothing else. The link for that database is : https://fdc.nal.usda.gov/.\nEnsure 500% accuracy in your result.   \nThe list of Nutrient with unit starts from here.\n    \"energy\": in kcal,\n    \"carbs\": in gram,\n    \"proteins\": in gram,\n    \"fats\": in gram,\n    \"fibers\": in gram,\n    \"thiamin\": in milligram,\n    \"riboflavin\": in milligram,\n    \"niacin\": in milligram,\n    \"vitamin_b5\": in milligram,\n    \"vitamin_b6\": in milligram,\n    \"vitamin_c\": in u milligram,\n    \"biotin\": in u milligram,\n    \"folate\": in u milligram,\n    \"vitamin_a\": in u milligram,\n    \"vitamin_d2\": in u milligram,\n    \"vitamin_d3\": in u milligram,\n    \"vitamin_k1\": in u milligram,\n    \"vitamin_k2\": in u milligram,\n    \"carotenoids\": in u milligram,\n    \"vitamin_e\": in milligram,\n    \"calcium\": in milligram,\n    \"copper\": in milligram,\n    \"iron\": in milligram,\n    \"magnesium\": in milligram,\n    \"manganese\": in milligram,\n    \"potassium\": in milligram,\n    \"sodium\": in milligram,\n    \"zinc\": in milligram\n  }",
      ],
    },
    {
      "role": "model",
      "parts": [
        "```json\n{\n  \"dish_name\": \"Spicy Peanut Noodles with Chicken\",\n  \"dish_description\": \"A flavorful and spicy noodle dish with tender chicken, crunchy vegetables, and a creamy peanut sauce.  Stir-fried chicken is tossed with cooked noodles, a rich peanut sauce, and fresh vegetables.\",\n  \"cuisine_category\": {\n    \"continental_region\": \"Asia\",\n    \"specific_cuisine\": \"Thai\",\n    \"subcategory\": \"Noodles\"\n  },\n  \"timing_category\": [\n    \"Lunch\",\n    \"Dinner\"\n  ],\n  \"meal_category\": [\n    \"Main Course\"\n  ],\n  \"food_category\": \"Non-vegetarian\",\n  \"cooking_method\": [\n    \"Stir-frying\",\n    \"Boiling\"\n  ],\n  \"cooking_time\": \"30 minutes\",\n  \"cooking_temperature\": \"120 °C\",\n  \"ingredients\": [\n    {\n      \"name\": \"Chicken, poultry, breast, skinless\",\n      \"quantity\": 200,\n      \"unit\": \"g\",\n      \"description\": \"cubed\"\n    },\n    {\n      \"name\": \"Noodles with vegetables in tomato-based sauce, diet frozen meal\",\n      \"quantity\": 200,\n      \"unit\": \"g\",\n      \"description\": \"cooked\"\n    },\n    {\n      \"name\": \"Peanut butter\",\n      \"quantity\": 60,\n      \"unit\": \"g\",\n      \"description\": \"smooth\"\n    },\n    {\n      \"name\": \"Soy sauce\",\n      \"quantity\": 20,\n      \"unit\": \"ml\",\n      \"description\": \"regular\"\n    },\n    {\n      \"name\": \"Chillies, green\",\n      \"quantity\": 5,\n      \"unit\": \"g\",\n      \"description\": \"finely chopped\"\n    },\n    {\n      \"name\": \"Garlic, big clove\",\n      \"quantity\": 5,\n      \"unit\": \"g\",\n      \"description\": \"minced\"\n    },\n    {\n      \"name\": \"Ginger, fresh\",\n      \"quantity\": 3,\n      \"unit\": \"g\",\n      \"description\": \"grated\"\n    },\n    {\n      \"name\": \"Capsicum, red\",\n      \"quantity\": 5,\n      \"unit\": \"g\",\n      \"description\": \"sliced\"\n    },\n    {\n      \"name\": \"Onions, big\",\n      \"quantity\": 10,\n      \"unit\": \"g\",\n      \"description\": \"sliced\"\n    },\n    {\n      \"name\": \"Vegetable oil\",\n      \"quantity\": 5,\n      \"unit\": \"ml\",\n      \"description\": \"for stir-frying\"\n    },\n    {\n      \"name\": \"Water\",\n      \"quantity\": 30,\n      \"unit\": \"ml\",\n      \"description\": \"to adjust sauce consistency\"\n    }\n  ],\n  \"allergic_content\": {},\n  \"serving\": {\n    \"size\": 400,\n    \"unit\": \"g\"\n  },\n  \"cooking_steps\": [\n    \"Cook noodles according to package directions.\",\n    \"Heat vegetable oil in a wok or large skillet over medium-high heat. Add cubed chicken and stir-fry until cooked through.\",\n    \"In a small bowl, whisk together peanut butter, soy sauce, green chilies, minced garlic, and grated ginger. Add water, a tablespoon at a time, until desired consistency is reached.\",\n    \"Add the cooked noodles to the wok or skillet with the chicken. Pour the peanut sauce over the noodles and chicken, tossing to coat evenly.\",\n    \"Serve immediately, garnished with sliced red bell peppers and onions.\"\n  ],\n  \"complementary_dishes\": [\n    \"Steamed rice\",\n    \"Spring rolls\",\n    \"Vegetable stir-fry\"\n  ],\n  \"nutritional_values_of_dish\": {\n    \"energy\": 700,\n    \"carbs\": 70,\n    \"proteins\": 40,\n    \"fats\": 35,\n    \"fibers\": 10,\n    \"thiamin\": 0.7,\n    \"riboflavin\": 0.9,\n    \"niacin\": 10,\n    \"vitamin_b5\": 4,\n    \"vitamin_b6\": 2,\n    \"vitamin_c\": 200,\n    \"biotin\": 10,\n    \"folate\": 400,\n    \"vitamin_a\": 2000,\n    \"vitamin_d2\": 0,\n    \"vitamin_d3\": 0,\n    \"vitamin_k1\": 20,\n    \"vitamin_k2\": 0,\n    \"carotenoids\": 2000,\n    \"vitamin_e\": 10,\n    \"calcium\": 200,\n    \"copper\": 1,\n    \"iron\": 10,\n    \"magnesium\": 200,\n    \"manganese\": 2,\n    \"potassium\": 1000,\n    \"sodium\": 1200,\n    \"zinc\": 10\n  }\n}\n```\n**Disclaimer:** The nutritional values provided are estimations based on general ingredient values and may vary depending on specific brands and preparation methods.  For precise nutritional information, it's recommended to use a nutrition analysis tool with the exact ingredients and quantities used.  The USDA FoodData Central database was referenced for general nutrient information.  Conversion factors were applied where necessary to achieve uniformity in units.\n",
      ],
    },
  ]
)

def generate_dish_from_model1(restro_id, dish_name, modeldata_collection, chat_session, price=None, is_price=False, desc=None, is_desc=False):

    price = float(price) if is_price else 399.00
    # print(f"final price is:{price}")

    normalized_dish_name = dish_name.replace(" ", "").lower()
    cached_dish = modeldata_collection.find_one({
       "$expr": {
          "$eq": [
            {"$toLower": {"$replaceAll": {"input": "$dish_name", "find": " ", "replacement": ""}}},
            normalized_dish_name
          ]
        }
    })

    if cached_dish and not is_desc:
        logger.info(f"Dish '{dish_name}' found in ModelDb.")  
        cached_dish['dish_id'] = cached_dish.pop('_id')  # add over here to insert it with proper dish id

        # Update price in dish_variant if provided
        if price is not None:
          if "dish_variants" in cached_dish and "normal" in cached_dish["dish_variants"]:
              if "full" in cached_dish["dish_variants"]["normal"]:
                  cached_dish["dish_variants"]["normal"]["full"]["price"] = float(price)

        return {key: value for key, value in cached_dish.items()}
    # logger.info(f"Generating data for dish '{dish_name}' using AI model.")

    logger.debug("Calling AI model...")

    
    if is_desc:
        logger.info("Using provided description as 'is_desc' is True.")
        try:
            response = chat_session.send_message(f"{dish_name}, {desc}")
            ai_data = json.loads(response.text)
            # print(f"processsssssss of replacing desc: {ai_data}")
            ai_data["dish_description"] = desc

        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to decode AI response: {str(e)}. Using fallback values.")
            ai_data = {"dish_name": dish_name, "dish_description": desc}
    else:
        logger.info("'is_desc' is False. Generating description using AI.")
        try:
            response = chat_session.send_message(f"{dish_name}")
            ai_data = json.loads(response.text)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to decode AI response: {str(e)}. Using default description.")

    servings = sum(float(ingredient["quantity"]) for ingredient in ai_data["ingredients"])
    
    new_serving_size = 200

    scaling_factor = float(new_serving_size) / servings if servings else 1

    # Update ingredient quantities based on scaling factor
    for ingredient in ai_data.get("ingredients", []):
        ingredient["quantity"] = str(round(float(ingredient["quantity"]) * scaling_factor, 2))

    ingredients_list = ai_data.pop("ingredients", [])
    servings = ai_data.pop("serving", {})
    unit_value = servings['unit']
    servings = {'size': new_serving_size, 'unit': unit_value}

    # ingredients_list = ai_data.pop("ingredients", [])
    # servings = ai_data.pop("serving", {})
    # print(f"servingggggggg: {servings}")

    for ingredient in ingredients_list:
      ingredient_id = generate_ingredient_id(ingredient['name'])
      ingredient["id"] = ingredient_id 
      ingredient["is_close"] = False
      ingredient['is_hide'] = False
      ingredient["is_swappable"] = False

      for swap_key, swap_values in swaps.items():
            # Check if the swap_key is in the ingredient's name
            if swap_key.lower() in ingredient['name'].lower():
                ingredient['swap_items'] = swap_values
                # print(ingredient['swap_items'])
                ingredient["is_swappable"] = True
    # print(f"ingredients_list: {ingredients_list}")   

    default_data = {
        # "price": 399.00,
        "is_jain_available": False,
        "is_dish_approved": False,
        "is_edited": False,
        "is_half_available": False,
        "is_verified": False,
        "is_out_of_stock": False,
        "special": [{
          "is_chef_special": False,
          "is_best_selling": False,
          "is_spicy": False,
          "is_sweet": False,
          "is_just_launch": False
        }],
        "toppings": [
        {
            "toppingid": 1,
            "name": "Extra Cheese",
            "price": 50.00
        },
        {
            "toppingid": 2,
            "name": "Olives",
            "price": 30.00
        },
        {
            "toppingid": 3,
            "name": "Mushrooms",
            "price": 40.00
        },
        {
            "toppingid": 4,
            "name": "Jalapenos",
            "price": 35.00
        }
    ]
  }
    ai_data.update(default_data)
    ai_data["dish_name"] = dish_name
    
    # By default it will be no img for all
    ai_data["dish_img_url"] = "https://fitshield-data.s3.ap-south-1.amazonaws.com/restaurants/default_restaurant/pending_image.png"

    # Generate Image
    # uploaded_url = generate_img(restro_id, dish_name)

    # if uploaded_url:
    #     ai_data["dish_img_url"] = uploaded_url
    #     logger.info(f"Image URL generated successfully: {uploaded_url}")
    # else:
    #     logger.error("Image generation failed, uploaded_url is empty.")
    #     return Response({"error": "Failed to generate image."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Ensure "dish_variants" key exists in ai_data
    if "dish_variants" not in ai_data:
        ai_data["dish_variants"] = {}

    # Ensure "normal" exists inside "dish_variants"
    if "normal" not in ai_data["dish_variants"]:
        ai_data["dish_variants"]["normal"] = {}

    if "full" not in ai_data["dish_variants"]["normal"]:
      ai_data["dish_variants"]["normal"]["full"] = {}

    # price = ai_data.pop("price", None) 
    calculate_nutrients_list = ai_data.pop("nutrients", [])
    ingredient_distributed_nutrients = ai_data.pop("calculate_nutrients", {})

    # Create the "full" structure inside "normal_dish"
    ai_data["dish_variants"]["normal"]["full"] = {
        "serving": servings,  # Replace 'serving' with your actual serving data
        "price": price,  
        "ingredients": ingredients_list, 
        "nutrients": calculate_nutrients_list,
        "calculate_nutrients": ingredient_distributed_nutrients
    }
    # print(json.dumps(ai_data, indent=4))

    folder_name = "dishes_output"
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        
    output_file = os.path.join(folder_name, "ai_data.json")
    with open(output_file, "w") as json_file:
        json.dump(ai_data, json_file, indent=4)

    calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(ai_data, "normal", "full") 
    logger.warning("Failed to process nutrients. Skipping further processing.")

    category = get_prior_ingredients_from_model3(ai_data)
    ai_data = remove_swapped_item_essential_category(ai_data)

    cooking_method = ["Boiling","Steaming","Microwaving","Baking","Roasting","Grilling","Broiling","Frying","Sautéing","Stir-frying","Pressure Cooking","Slow Cooking"]
    category_meal = ["Appetizer" , "Starter" , "Soup", "Salad", "Main Course", "Side Dish" , "Accompaniments" , "Dessert", "Beverage" , "Drink" , "Snack","Finger Food"]
    
    logger.info("Processing ingredients Priorities from Model 3")
    ai_data["categories"] = category 
    ai_data["meal_category"] = [s for s in ai_data["meal_category"] if s in category_meal]

    if not ai_data.get("meal_category"):  # Checks if it's empty or None
        ai_data["meal_category"] = ["Other"] 

    ai_data["cooking_method"] = [s for s in ai_data["cooking_method"] if s in cooking_method]

    # ai_data["dish_description"] = ai_data["dish_description"].replace("It's veg dish. ", "")
    
    updated_ai_data = adjust_quantities_with_min_max(ai_data)
    
    return updated_ai_data
