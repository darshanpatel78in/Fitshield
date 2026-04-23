# import logging
# import random
# import google.generativeai as genai
# import json
# import copy


# from fitshield_webapp.AI.AIModel.ai_image_model import generate_img
# from fitshield_webapp.AI.AIModel.ai_model2 import process_ingredients_nutrients_from_model2
# from rest_framework import status
# from rest_framework.response import Response

# from fitshield_webapp.AI.AIModel.ai_model3 import get_prior_ingredients_from_model3
# from fitshield_webapp.utils.generate_id import generate_dish_id, generate_ingredient_id
# import nltk
# nltk.download('punkt_tab')
# from .model_helpers.ingredients_swaps import swaps

# import logging
# logging.basicConfig(
#     level=logging.DEBUG,  
#     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)





# # Model 1
# genai.configure(api_key="AIzaSyC7PuTD0r_KKmKwqcnqpZTeA0-84bOSj24")
# generation_config = {
#     "temperature": 1,
#     "top_p": 0.95,
#     "top_k": 64,
#     "max_output_tokens": 8192,
#     "response_mime_type": "application/json",
# }

# model = genai.GenerativeModel(
#   model_name="gemini-1.5-flash",
#   generation_config=generation_config,
#   system_instruction="Generate a JSON object for a dish based on the following inputs:\n1.\tdish_name: Name of the dish.\n2.\tfood_category: Specifies whether the dish is vegetarian or non-vegetarian.\n3.\tis_jain: Indicates if the dish is Jain-compliant:\no\tIf is_jain is \"jain\", exclude root vegetables (e.g., onions, garlic, potatoes, etc.) and any ingredients not allowed in Jain cuisine.\no\tIf is_jain is \"non-jain\", follow the regular dietary guidelines for the selected food category.\nThe JSON object should include:\n{\n  \"dish_name\": \"__\",\n  \"dish_description\": \"__\",\n  \"cuisine_category\": {\n    \"continental_region\": \"__\",\n    \"specific_cuisine\": \"__\",\n    \"subcategory\": \"__\"\n  },\n  \"timing_category\": [\n    \"__\"\n  ],\n  \"meal_category\": [\n    \"__\"\n  ],\n  \"food_category\": \"__\",\n  \"cooking_method\": [\n    \"__\"\n  ],\n  \"cooking_time\": \"__\",\n  \"cooking_temperature\": \"__\",\n  \"ingredients\": [\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    },\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    },\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    }\n  ],\n  \"allergic_content\": {},\n  \"serving\": {\n    \"size\": \"__\",\n    \"unit\": \"__\"\n  },\n  \"cooking_steps\": [\n    \"__\",\n    \"__\",\n    \"__\"\n  ]\n  \"complementary_dishes\": [\n    \"__\",\n    \"__\",\n    \"__\"\n  ]\n}\n",
# )

# chat_session = model.start_chat(
#   history=[
#     {
#       "role": "user",
#       "parts": [
#         "You are a highly skilled culinary expert and food data analyst specializing in generating detailed dish information in JSON format. Your expertise includes correcting dish names (regardless of language or spelling variations) and presenting comprehensive details such as description, ingredients, cooking steps, and dietary information.\nInput Details:\n1.\tdish_name: Correct any spelling errors and identify the dish name, regardless of language.\n2.\tfood_category: Specifies whether the dish is vegetarian or non-vegetarian.\n3.\tis_jain: Indicates if the dish is Jain-compliant:\no\tIf \"jain\", exclude root vegetables (e.g., onions, garlic, potatoes) and other non-compliant ingredients.\no\tIf \"non-jain\", follow regular dietary guidelines for the selected food category.\nJSON Output Requirements:\n1.\tdish_name: Corrected name of the dish.\n2.\tdish_description: If provided, use this description directly to extract and must include all ingredients and cooking methods. Otherwise, A description to be generated between 20 to 200 characters highlighting main ingredients, flavor profile, and preparation style. Avoid excessive special characters.\n3.\tcuisine_category:\no\tcontinental_region: Validate against predefined regions (e.g., Asia, Europe, North America).\no\tspecific_cuisine: Match predefined cuisines within the selected region.\no\tsubcategory: Validate subcategories under the cuisine (e.g., \"North Indian\" for Indian cuisine).\n4.\ttiming_category: Select applicable options:\no\tBreakfast, Lunch, Snack, Dinner, Brunch, Midnight Snack\no\tUse: \"timing_category\": [\"__\"] for a single category or multiple options.\n5.\tmeal_category: If  provided, take it or select one or more applicable options:\no\tAppetizer/Starter, Soup/Salad, Main Course, Side Dish/Accompaniments, Dessert, Beverage/Drink, Snack/Finger Food\n6.\tcooking_method: If the description includes cooking methods, extract the primary method from it.\nIf the description does not include methods, extract them from the provided cooking steps.\nIf both are unavailable or inconclusive, infer a generic cooking method using an LLM. Choose one or more methods from below list:\no\tBoiling, Steaming, Baking, Grilling, Frying, Sautéing, Pressure Cooking, Slow Cooking\n7.\tcooking_time: Provide time in standard format (e.g., \"45 minutes\") and validate against these ranges:\no\tQuick Cook: Under 30 minutes\no\tMedium Cook: 30–60 minutes\no\tLong Cook: 1–3 hours\no\tExtended Cook: Over 3 hours\n8.\tcooking_temperature: Provide in °C or °F, ensuring values are within valid ranges (e.g., 50°C–500°C). Convert Fahrenheit to Celsius if necessary.\n9.\tingredients: A detailed list of ingredients including:\no\tname: Standardized English name.\no\tquantity: Exact value ensuring total is 200g/ml based on dish type.\no\tunit: g (grams) or ml (millilitres).\no\tdescription: Ingredient state (e.g., \"chopped,\" \"boiled\").\nExample:\n{\n\"name\": \"Rice\",\n\"quantity\": \"50\",\n\"unit\": \"g\",\n\"description\": \"chopped\"\n}\n10.\tallergic_content: Leave this field empty. \n11.\tserving: Calculate serving size based on ingredient quantities. Consolidate into grams or milliliters. Example:\n{\n  \"size\": \"223\",\n  \"unit\": \"g\"\n}\n12.\tcooking_steps: Provide detailed, step-by-step cooking instructions. Example:\n[\n  \"1. Rinse rice and moong dal thoroughly.\",\n  \"2. Combine rice and dal with water in a pan and bring to a boil.\",\n  \"3. Heat ghee in another pan and sauté spices.\",\n  \"4. Mix the spice mixture into the cooked khichdi and stir well.\"\n]\n13. complementary_dishes : Find out complementary dishes from \"dish_description\" or \"dish_name\". I want complementary dishes in list format.\nKey Notes:\n•\tEnsure the dish details are tailored to the inputs (dish_name, food_category, and is_jain).\n•\tValidate all inputs and ensure accuracy in the generated JSON.\n•\tI only want json object in response nothing else.",
#       ],
#     },
#     {
#       "role": "model",
#       "parts": [
#         "```json\n{\n  \"dish_name\": \"Aloo Gobi Masala\",\n  \"dish_description\": \"Aloo Gobi Masala is a flavorful and aromatic Indian dish made with potatoes and cauliflower. The vegetables are cooked with a blend of spices, creating a hearty and satisfying meal.\",\n  \"cuisine_category\": {\n    \"continental_region\": \"Asia\",\n    \"specific_cuisine\": \"Indian\",\n    \"subcategory\": \"North Indian\"\n  },\n  \"timing_category\": [\n    \"Lunch\",\n    \"Dinner\"\n  ],\n  \"meal_category\": [\n    \"Main Course\"\n  ],\n  \"food_category\": \"Vegetarian\",\n  \"cooking_method\": [\n    \"Sautéing\"\n  ],\n  \"cooking_time\": \"45 minutes\",\n  \"cooking_temperature\": \"180°C\",\n  \"ingredients\": [\n    {\n      \"name\": \"Potatoes\",\n      \"quantity\": \"100\",\n      \"unit\": \"g\",\n      \"description\": \"cubed\"\n    },\n    {\n      \"name\": \"Cauliflower\",\n      \"quantity\": \"100\",\n      \"unit\": \"g\",\n      \"description\": \"florets\"\n    },\n    {\n      \"name\": \"Onions\",\n      \"quantity\": \"20\",\n      \"unit\": \"g\",\n      \"description\": \"finely chopped\"\n    },\n    {\n      \"name\": \"Tomatoes\",\n      \"quantity\": \"30\",\n      \"unit\": \"g\",\n      \"description\": \"pureed\"\n    },\n    {\n      \"name\": \"Ginger-Garlic Paste\",\n      \"quantity\": \"10\",\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Turmeric Powder\",\n      \"quantity\": \"2\",\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Chili Powder\",\n      \"quantity\": \"2\",\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Cumin Powder\",\n      \"quantity\": \"2\",\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Coriander Powder\",\n      \"quantity\": \"3\",\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Garam Masala\",\n      \"quantity\": \"1\",\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Oil\",\n      \"quantity\": \"10\",\n      \"unit\": \"ml\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Salt\",\n      \"quantity\": \"2\",\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Water\",\n      \"quantity\": \"50\",\n      \"unit\": \"ml\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Cilantro\",\n      \"quantity\": \"5\",\n      \"unit\": \"g\",\n      \"description\": \"chopped, for garnish\"\n    }\n\n  ],\n  \"allergic_content\": {},\n  \"serving\": {\n    \"size\": \"200\",\n    \"unit\": \"g\"\n  },\n  \"cooking_steps\": [\n    \"1. Heat oil in a pan. Add onions and saute until golden brown.\",\n    \"2. Add ginger-garlic paste and saute for a minute.\",\n    \"3. Add turmeric powder, chili powder, cumin powder, coriander powder, and garam masala. Saute for 30 seconds.\",\n    \"4. Add potatoes and cauliflower. Mix well and cook for 5 minutes.\",\n    \"5. Add tomato puree and salt. Mix well and cook for 5 minutes.\",\n    \"6. Add water, cover the pan, and cook for 15-20 minutes or until the vegetables are tender.\",\n    \"7. Garnish with cilantro and serve hot.\"\n  ],\n  \"complementary_dishes\": [\n    \"Naan\",\n    \"Roti\",\n    \"Rice\"\n  ]\n}\n```\n",
#       ],
#     },
#   ]
# )
# # system_instruction = """
# # You are a highly skilled culinary expert and food data analyst with extensive experience in generating detailed dish information in JSON format. Your specialty lies in correcting dish names regardless of language or spelling variations and presenting comprehensive details about the dish, including its description, ingredients, cooking steps, and any relevant dietary information. Your task is to generate a JSON object for the dish based on the provided inputs: dish_name, food_category, and is_jain. The food_category determines whether the dish is vegetarian or non-vegetarian. Ensure the ingredients and description match this category. The is_jain input specifies whether the dish is Jain-compliant. If is_jain is "jain," exclude root vegetables (e.g., onions, garlic, potatoes, etc.) and any ingredients not allowed in Jain cuisine. If is_jain is "non-jain," the dish can follow the regular dietary guidelines for the selected food category.

# # Include the following details in your output:

# # {
# #   "dish_name": "__",
# #   "dish_description": "__",
# #   "cuisine_category": {
# #     "continental_region": "__",
# #     "specific_cuisine": "__",
# #     "subcategory": "__"
# #   },
# #   "timing_category": [
# #     "__"
# #   ],
# #   "meal_category": [
# #     "__"
# #   ],
# #   "food_category": "__",
# #   "cooking_method": [
# #     "__"
# #   ],
# #   "cooking_time": "__",
# #   "cooking_temperature": "__",
# #   "ingredients": [
# #     {
# #       "name": "__",
# #       "quantity": "__",
# #       "unit": "__",
# #       "description": "__"
# #     },
# #     {
# #       "name": "__",
# #       "quantity": "__",
# #       "unit": "__",
# #       "description": "__"
# #     },
# #     {
# #       "name": "__",
# #       "quantity": "__",
# #       "unit": "__",
# #       "description": "__"
# #     }
# #   ],
# #   "allergic_content": {},
# #   "serving": {
# #       "size": "__",
# #       "unit": "__"
# #     },
# #   "cooking_steps": [
# #     "__",
# #     "__",
# #     "__"
# #   ]
# # }

# # Ensure the `serving` field includes the following:
# # 1. `full_serving`: Representing the provided full serving size and its unit.
# # 2. `half_serving`: Automatically calculated by dividing the `full_serving` size by 2 while retaining the same unit.
# # """)

# chat_session = model.start_chat(
#   history=[
#     {
#       "role": "user",
#       "parts": [
#         "You are a highly skilled culinary expert and food data analyst with extensive experience in generating detailed dish information in JSON format. Your specialty lies in correcting dish names regardless of language or spelling variations and presenting comprehensive details about the dish, including its description, ingredients, cooking steps, and any relevant dietary information. Your task is to generate a JSON object for the dish based on the provided inputs: dish_name, food_category, and is_jain. The food_category determines whether the dish is vegetarian or non-vegetarian. Ensure the ingredients and description match this category. The is_jain input specifies whether the dish is Jain-compliant. If is_jain is \"jain,\" exclude root vegetables (e.g., onions, garlic, potatoes, etc.) and any ingredients not allowed in Jain cuisine. If is_jain is \"non-jain,\" the dish can follow the regular dietary guidelines for the selected food category.\n\nInclude the following details in your output:\n\ndish_name: Correct any spelling errors and identify the dish name regardless of the language.\ndish_description: If provided, use this description directly to extract and must include all ingredients and cooking methods. Otherwise, A description to be generated between 20 to 200 characters highlighting main ingredients, flavor profile, and preparation style. Avoid excessive special characters.\ncuisine_category: Provide the following:\ncontinental_region: Validate against predefined regions (Asia, Europe, Africa, North America, South America, Middle East, Oceania).\nspecific_cuisine: Match a predefined list of cuisines associated with the selected continental region.\nsubcategory: Match a predefined list of subcategories under the selected cuisine. For example, for Indian cuisine, acceptable subcategories are North Indian, South Indian, and Indo-Chinese, rejecting typos like \"Nort India.\"\ntiming_category: Choose applicable options (Breakfast, Lunch, Snack, Dinner, Brunch, Midnight Snack). For a single method, use: \"timing_category\": [\"__\"]. For multiple methods, use: \"timing_category\": [\"\", \"\"].\nmeal_category: Choose one or more applicable options (Appetizer/Starter, Soup/Salad, Main Course, Side Dish/Accompaniments, Dessert, Beverage/Drink, Snack/Finger Food). Use the same format as timing_category.\ncooking_method: Select from options like Boiling, Steaming, Microwaving, Baking, Grilling, Frying, Sautéing, Pressure Cooking, and Slow Cooking. Use a single method or multiple methods as needed.\ncooking_time: Provide in standard format (e.g., \"45 minutes\") and validate the range based on cooking time categories: Quick Cook (under 30 minutes), Medium Cook (30–60 minutes), Long Cook (1–3 hours), and Extended Cook (Over 3 hours). Handle missing units or approximate descriptions appropriately.\ncooking_temperature: Provide in °C or °F, ensuring the range is valid (50°C–500°C or 120°F–770°F). Standardize the unit and convert Fahrenheit to Celsius if detected.\ningredients: Generate a precise list of ingredients with standardized English names and quantities. Ensure that the total quantity of ingredients equals 200g or 200ml based on whether the dish is solid or fluid. Include a \"description\" key for each ingredient, detailing preparation or condition (e.g., \"chopped,\" \"boiled,\" \"grilled\"). For example:\n\"ingredients\": [\n  {\n    \"name\": \"Rice\",\n    \"quantity\": \"50\",\n    \"unit\": \"g\",\n    \"description\": \"washed\"\n  },\n  {\n    \"name\": \"Moong Dal (Split Yellow Lentils)\",\n    \"quantity\": \"50\",\n    \"unit\": \"g\",\n    \"description\": \"soaked\"\n  },\n  {\n    \"name\": \"Tomato\",\n    \"quantity\": \"5\",\n    \"unit\": \"g\",\n    \"description\": \"finely chopped\"\n  },\n  {\n    \"name\": \"Turmeric Powder\",\n    \"quantity\": \"1\",\n    \"unit\": \"g\",\n    \"description\": \"as seasoning\"\n  }\n]\nallergic_content: Correct any potential misspellings and provide allergen information based on predefined categories (e.g., Milk and Dairy Products, Peanuts, Soybeans). Use JSON format for detected allergens and their categories.\nserving: Calculate the total serving size based on ingredient quantities, consolidated into a common unit (either grams or milliliters). For example:\n\"serving\": {\n  \"size\": \"223\",\n  \"unit\": \"g\"\n}\ncooking_steps: Provide detailed, numbered cooking instructions in the format:\n\"cooking_steps\": [\n  \"1. Rinse rice and moong dal thoroughly.\",\n  \"2. In a pan, combine rice and dal with water and bring to a boil.\",\n  \"3. Heat ghee in a separate pan. Add asafoetida and spices.\",\n  \"4. Whisk yogurt and mix into the spice mixture. Simmer for 5 minutes.\",\n  \"5. Combine the yogurt gravy with the cooked khichdi and mix gently.\"\n]\nEnsure accuracy, validate all inputs, and structure the output in the specified JSON format. Adapt the dish details based on the provided inputs (dish_name, food_category, and is_jain).",
#       ],
#     },
#     {
#       "role": "model",
#       "parts": [
#         "```json\n{\n  \"dish_name\": \"Vegetable Curry\",\n  \"dish_description\": \"A flavorful mix of fresh vegetables cooked in a rich tomato-based gravy, seasoned with aromatic spices.\",\n  \"cuisine_category\": {\n    \"continental_region\": \"Asia\",\n    \"specific_cuisine\": \"Indian\",\n    \"subcategory\": \"North Indian\"\n  },\n  \"timing_category\": [\n    \"Lunch\",\n    \"Dinner\"\n  ],\n  \"meal_category\": [\n    \"Main Course\",\n     \"Side Dish/Accompaniments\"\n  ],\n  \"food_category\": \"vegetarian\",\n   \"cooking_method\": [\n    \"Sautéing\",\n    \"Simmering\"\n  ],\n  \"cooking_time\": \"40 minutes\",\n  \"cooking_temperature\": \"180°C\",\n  \"ingredients\": [\n    {\n      \"name\": \"Carrot\",\n      \"quantity\": \"50\",\n      \"unit\": \"g\",\n      \"description\": \"diced\"\n    },\n    {\n      \"name\": \"Green Beans\",\n      \"quantity\": \"40\",\n      \"unit\": \"g\",\n      \"description\": \"chopped\"\n    },\n    {\n      \"name\": \"Cauliflower\",\n      \"quantity\": \"50\",\n      \"unit\": \"g\",\n      \"description\": \"cut into florets\"\n    },\n        {\n      \"name\": \"Tomato\",\n       \"quantity\": \"40\",\n      \"unit\": \"g\",\n       \"description\": \"pureed\"\n    },\n       {\n      \"name\": \"Spinach\",\n      \"quantity\": \"20\",\n      \"unit\":\"g\",\n      \"description\": \"chopped\"\n        } ,\n    {\n     \"name\": \"Ginger\",\n      \"quantity\": \"1\",\n      \"unit\": \"g\",\n       \"description\": \"grated\"\n    },\n    {\n      \"name\": \"Green Chili\",\n       \"quantity\": \"1\",\n      \"unit\": \"g\",\n      \"description\":\"sliced\"\n    },\n     {\n      \"name\": \"Cumin Seeds\",\n      \"quantity\": \"1\",\n      \"unit\": \"g\",\n      \"description\":\"as seasoning\"\n    },\n       {\n      \"name\": \"Turmeric Powder\",\n       \"quantity\": \"1\",\n      \"unit\": \"g\",\n      \"description\":\"as seasoning\"\n    },\n      {\n        \"name\": \"Coriander powder\",\n        \"quantity\":\"1\",\n        \"unit\": \"g\",\n        \"description\": \"as seasoning\"\n      },\n    {\n      \"name\": \"Salt\",\n      \"quantity\": \"5\",\n      \"unit\": \"g\",\n      \"description\": \"to taste\"\n    }\n  ],\n  \"allergic_content\": {},\n  \"serving\": {\n    \"size\": \"200\",\n    \"unit\": \"g\"\n  },\n  \"cooking_steps\": [\n    \"1. Heat oil in a pan. Add cumin seeds and let them splutter.\",\n     \"2. Add ginger and green chili and sauté for a minute.\",\n    \"3. Add the pureed tomatoes and cook until the oil starts separating.\",\n    \"4. Add all the dry spices - turmeric powder, coriander powder, and salt. Mix well.\",\n    \"5. Add all the vegetables and saute for 5 minutes.\",\n     \"6. Add water to cover the vegetables and bring to a boil.\",\n     \"7. Reduce the heat and let it simmer until the vegetables are cooked.\",\n      \"8. Add chopped spinach and simmer for 2 minutes. Serve hot.\"\n  ]\n}\n```\n",
#       ],
#     },
#     {
#       "role": "user",
#       "parts": [
#         "biryani, non-veg, non-jain",
#       ],
#     },
#     {
#       "role": "model",
#       "parts": [
#         "```json\n{\n  \"dish_name\": \"Biryani\",\n  \"dish_description\": \"Aromatic rice dish with marinated chicken, layered with fragrant spices, herbs, and saffron, slow-cooked to perfection.\",\n  \"cuisine_category\": {\n    \"continental_region\": \"Asia\",\n    \"specific_cuisine\": \"Indian\",\n    \"subcategory\": \"Mughlai\"\n  },\n  \"timing_category\": [\n    \"Lunch\",\n    \"Dinner\"\n  ],\n  \"meal_category\": [\n    \"Main Course\"\n  ],\n  \"food_category\": \"non-vegetarian\",\n  \"cooking_method\": [\n    \"Slow Cooking\",\n    \"Steaming\"\n  ],\n  \"cooking_time\": \"90 minutes\",\n  \"cooking_temperature\": \"160°C\",\n  \"ingredients\": [\n    {\n      \"name\": \"Basmati Rice\",\n      \"quantity\": \"100\",\n      \"unit\": \"g\",\n      \"description\": \"soaked\"\n    },\n    {\n      \"name\": \"Chicken\",\n      \"quantity\": \"50\",\n      \"unit\": \"g\",\n      \"description\": \"marinated\"\n    },\n    {\n      \"name\": \"Onion\",\n      \"quantity\": \"15\",\n      \"unit\": \"g\",\n      \"description\": \"sliced\"\n    },\n        {\n      \"name\": \"Yogurt\",\n      \"quantity\": \"10\",\n      \"unit\": \"ml\",\n      \"description\": \"whisked\"\n    },\n    {\n      \"name\": \"Ginger-Garlic Paste\",\n      \"quantity\": \"10\",\n      \"unit\": \"g\",\n      \"description\": \"freshly made\"\n    },\n    {\n      \"name\": \"Ghee\",\n      \"quantity\": \"5\",\n       \"unit\": \"ml\",\n      \"description\": \"for cooking\"\n    },\n        {\n      \"name\": \"Mint Leaves\",\n      \"quantity\": \"3\",\n      \"unit\": \"g\",\n      \"description\": \"fresh\"\n    },\n     {\n      \"name\": \"Coriander Leaves\",\n       \"quantity\": \"3\",\n      \"unit\": \"g\",\n      \"description\": \"fresh\"\n    },\n    {\n       \"name\": \"Green Chilies\",\n      \"quantity\": \"1\",\n      \"unit\":\"g\",\n      \"description\": \"sliced\"\n    },\n      {\n      \"name\": \"Biryani Spices\",\n      \"quantity\": \"2\",\n      \"unit\": \"g\",\n      \"description\": \"blend\"\n    }\n  ],\n    \"allergic_content\": {\n        \"Milk and Dairy Products\": [\"Yogurt\"]\n    },\n  \"serving\": {\n    \"size\": \"200\",\n    \"unit\": \"g\"\n  },\n  \"cooking_steps\": [\n    \"1. Marinate chicken with yogurt, ginger-garlic paste, and biryani spices for at least 30 minutes.\",\n    \"2. In a heavy-bottomed pot, heat ghee and sauté sliced onions until golden brown.\",\n    \"3. Add the marinated chicken and cook for 5 minutes.\",\n    \"4. Layer half-cooked rice over the chicken.\",\n    \"5. Sprinkle mint leaves, coriander leaves, and green chilies.\",\n    \"6. Cover the pot and cook on low heat for 30-40 minutes or until the rice and chicken are fully cooked.\",\n     \"7. Let it rest for 10 minutes before serving.\"\n  ]\n}\n```\n",
#       ],
#     },
#   ]
# )

# def generate_dish_from_model1(restro_id, dish_name, modeldata_collection, chat_session, desc = None, is_desc = False): 
#     normalized_dish_name = dish_name.replace(" ", "").lower()
#     cached_dish = modeldata_collection.find_one({
#        "$expr": {
#           "$eq": [
#             {"$toLower": {"$replaceAll": {"input": "$dish_name", "find": " ", "replacement": ""}}},
#             normalized_dish_name
#           ]
#         }
#     })
#     # Catch in base format and convert in varient->normal->full
#     if cached_dish and not is_desc:
#         logger.info(f"Dish '{dish_name}' found in ModelDb.")  
#         cached_dish['dish_id'] = cached_dish.pop('_id')  # add over here to insert it with proper dish id
#         return {key: value for key, value in cached_dish.items()}
#     # logger.info(f"Generating data for dish '{dish_name}' using AI model.")

#     logger.debug("Calling AI model...")

#     if is_desc:
#         print("che desc as per flag pn")
#         logger.info("Using provided description as 'is_desc' is True.")
#         try:
#             print("haloo to use kriee aej???")
#             response = chat_session.send_message(f"{dish_name}, {desc}")
#             ai_data = json.loads(response.text)
#             print(f"processsssssss of replacing desc: {ai_data}")
#             ai_data["dish_description"] = desc

#         except (json.JSONDecodeError, AttributeError) as e:
#             logger.error(f"Failed to decode AI response: {str(e)}. Using fallback values.")
#             ai_data = {"dish_name": dish_name, "dish_description": desc}
#     else:
#         logger.info("'is_desc' is False. Generating description using AI.")
#         try:
#             print("nthi halooo kro generate")
#             response = chat_session.send_message(f"{dish_name}")
#             ai_data = json.loads(response.text)
#             print(f"lets seee{ai_data}")
#         except (json.JSONDecodeError, AttributeError) as e:
#             logger.error(f"Failed to decode AI response: {str(e)}. Using default description.")

#     print("beforeeee poppopopo")
#     ingredients_list = ai_data.pop("ingredients", [])
#     servings = ai_data.pop("serving", {})
#     print(ingredients_list)
#     for ingredient in ingredients_list:
#       ingredient_id = generate_ingredient_id(ingredient['name'])
#       ingredient["id"] = ingredient_id 
#       ingredient["is_close"] = False
#       ingredient['is_hide'] = False
#       ingredient["is_swappable"] = False

#       for swap_key, swap_values in swaps.items():
#             # Check if the swap_key is in the ingredient's name
#             if swap_key.lower() in ingredient['name'].lower():
#                 ingredient['swap_items'] = swap_values
#                 print(ingredient['swap_items'])
#                 ingredient["is_swappable"] = True

#     default_data = {
#         "price": 399.00,
#         "is_jain_available": False,
#         "is_edited": False,
#         "is_half_available": False,
#         "is_verified": False,
#         "is_out_of_stock": False,
#         "special": [{
#           "is_chef_special": False,
#           "is_best_selling": False,
#           "is_spicy": False,
#           "is_sweet": False,
#           "is_just_launch": False
#         }],
#         "toppings": [
#         {
#             "toppingid": 1,
#             "name": "Extra Cheese",
#             "price": 50.00
#         },
#         {
#             "toppingid": 2,
#             "name": "Olives",
#             "price": 30.00
#         },
#         {
#             "toppingid": 3,
#             "name": "Mushrooms",
#             "price": 40.00
#         },
#         {
#             "toppingid": 4,
#             "name": "Jalapenos",
#             "price": 35.00
#         }
#     ]
#   }
#     ai_data.update(default_data)
#     ai_data["dish_name"] = dish_name
    
#     uploaded_url = generate_img(restro_id, dish_name)

#     if uploaded_url:
#         ai_data["dish_img_url"] = uploaded_url
#         logger.info(f"Image URL generated successfully: {uploaded_url}")
#     else:
#         logger.error("Image generation failed, uploaded_url is empty.")
#         return Response({"error": "Failed to generate image."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     # Ensure "dish_variants" key exists in ai_data
#     if "dish_variants" not in ai_data:
#         ai_data["dish_variants"] = {}

#     # Ensure "normal" exists inside "dish_variants"
#     if "normal_dish" not in ai_data["dish_variants"]:
#         ai_data["dish_variants"]["normal"] = {}

#     ai_data["dish_variants"]["normal"]["ingredients"] = ingredients_list
    
#     price = ai_data.pop("price", None)
#     calculate_nutrients_list = ai_data.pop("nutrients", [])
#     ingredient_distributed_nutrients = ai_data.pop("calculate_nutrients", {})
#     print(calculate_nutrients_list)
    
#     print(f"ai data in model 1: {ai_data}")
#     calculate_nutrients_list, ingredient_distributed_nutrients = process_ingredients_nutrients_from_model2(ai_data)
#     if not calculate_nutrients_list and not ingredient_distributed_nutrients:
#       logger.warning("Failed to process nutrients. Skipping further processing.")

#     # Create the "full" structure inside "normal_dish"
#     ai_data["dish_variants"]["normal"]["full"] = {
#         "serving": servings,  # Replace 'serving' with your actual serving data
#         "price": price,  
#         "ingredients": ingredients_list, 
#         "nutrients": calculate_nutrients_list,
#         "calculate_nutrients": ingredient_distributed_nutrients
#     }
#     category = get_prior_ingredients_from_model3(dish_name,ai_data, ingredients_list)
#     logger.info("Processing ingredients Priorities from Model 3")
#     ai_data["categories"] = category  

#     print("finalllllllllllllllllllllllll")
#     print(json.dumps(ai_data, indent=4)) 
#     return ai_data

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
from fitshield_webapp.AI.AIModel.model_helpers.ingredients_swaps import swaps

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
  print(f"Uploaded file '{file.display_name}' as: {file.uri}")
  return file

def wait_for_files_active(files):

  print("Waiting for file processing...")
  for name in (file.name for file in files):
    file = genai.get_file(name)
    while file.state.name == "PROCESSING":
      print(".", end="", flush=True)
      time.sleep(10)
      file = genai.get_file(name)
    if file.state.name != "ACTIVE":
      raise Exception(f"File {file.name} failed to process")
  print("...all files ready")
  print()


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
  system_instruction="Generate a JSON object for a dish based on the following inputs:\n1.\tdish_name: Name of the dish.\n2.\tfood_category: Specifies whether the dish is Vegetarian or Non-vegetarian.\n3.\tis_jain: Indicates if the dish is Jain-compliant:\no\tIf is_jain is \"jain\", exclude root vegetables (e.g., onions, garlic, potatoes, etc.) and any ingredients not allowed in Jain cuisine.\no\tIf is_jain is \"non-jain\", follow the regular dietary guidelines for the selected food category.\nThe JSON object should include:\n{\n  \"dish_name\": \"__\",\n  \"dish_description\": \"__\",\n  \"cuisine_category\": {\n    \"continental_region\": \"__\",\n    \"specific_cuisine\": \"__\",\n    \"subcategory\": \"__\"\n  },\n  \"timing_category\": [\n    \"__\"\n  ],\n  \"meal_category\": [\n    \"__\"\n  ],\n  \"food_category\": \"__\",\n  \"cooking_method\": [\n    \"__\"\n  ],\n  \"cooking_time\": \"__\",\n  \"cooking_temperature\": \"__\",\n  \"ingredients\": [\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    },\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    },\n    {\n      \"name\": \"__\",\n      \"quantity\": \"__\",\n      \"unit\": \"__\",\n      \"description\": \"__\"\n    }\n  ],\n  \"allergic_content\": {},\n  \"serving\": {\n    \"size\": \"__\",\n    \"unit\": \"__\"\n  },\n  \"cooking_steps\": [\n    \"__\",\n    \"__\",\n    \"__\"\n  ]\n  \"complementary_dishes\": [\n    \"__\",\n    \"__\",\n    \"__\"\n  ]\n}\n\nIngredient Database:\n\nNote: You must reference a pre-existing text file containing ingredient names whenever generating the dish's ingredients list. The ingredient names in this file should be considered valid, and you must use those exact names for all ingredients.",
)



# files = [
#   upload_to_gemini("D:\\Fitshield\\fitshield\\fitshield_webapp\\AI\\AIModel\\food_names.txt", mime_type="text/plain"),
# ]

# Get the dynamic path to the file based on the current working directory
def get_file_path(filename):
    # Get the current working directory (where the script is running)
    base_dir = os.path.dirname(os.path.abspath(__file__))  # To get the current script's directory
    
    # Dynamically create the path to the file in the AIModel directory
    print(f"base_dir: {base_dir}")
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
        "```json\n{\n  \"dish_name\": \"Jain Spiced Quinoa Salad\",\n  \"dish_description\": \"A flavorful and healthy salad featuring quinoa, mixed greens, and a vibrant blend of Jain-friendly spices.\",\n  \"cuisine_category\": {\n    \"continental_region\": \"Asian\",\n    \"specific_cuisine\": \"Indian-inspired\",\n    \"subcategory\": \"Salad\"\n  },\n  \"timing_category\": [\n    \"Anytime\"\n  ],\n  \"meal_category\": [\n    \"Lunch\",\n    \"Dinner\",\n    \"Side Dish\"\n  ],\n  \"food_category\": \"Vegetarian\",\n  \"is_jain\": \"jain\",\n  \"cooking_method\": [\n    \"Boiling\",\n    \"Mixing\"\n  ],\n  \"cooking_time\": \"20 minutes\",\n  \"cooking_temperature\": \"212°F (100°C)\",\n  \"ingredients\": [\n    {\n      \"name\": \"Quinoa\",\n      \"quantity\": 1,\n      \"unit\": \"cup\",\n      \"description\": \"Rinsed quinoa\"\n    },\n    {\n      \"name\": \"Water\",\n      \"quantity\": 1.5,\n      \"unit\": \"cups\",\n      \"description\": \"For boiling quinoa\"\n    },\n    {\n      \"name\": \"Amaranth leaves, green\",\n      \"quantity\": 1,\n      \"unit\": \"cup\",\n      \"description\": \"Chopped\"\n    },\n    {\n      \"name\": \"Spinach\",\n      \"quantity\": 1,\n      \"unit\": \"cup\",\n      \"description\": \"Chopped\"\n    },\n    {\n      \"name\": \"Coriander leaves\",\n      \"quantity\": 0.5,\n      \"unit\": \"cup\",\n      \"description\": \"Chopped\"\n    },\n    {\n      \"name\": \"Ginger, fresh\",\n      \"quantity\": 1,\n      \"unit\": \"tsp\",\n      \"description\": \"Grated\"\n    },\n    {\n      \"name\": \"Cardamom, green\",\n      \"quantity\": 2,\n      \"unit\": \"pods\",\n      \"description\": \"Finely ground\"\n    },\n    {\n      \"name\": \"Cumin seeds\",\n      \"quantity\": 0.5,\n      \"unit\": \"tsp\",\n      \"description\": \"Ground\"\n    },\n    {\n      \"name\": \"Turmeric powder\",\n      \"quantity\": 0.25,\n      \"unit\": \"tsp\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Salt\",\n      \"quantity\": \"to taste\",\n      \"unit\": \"\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Lemon juice\",\n      \"quantity\": 1,\n      \"unit\": \"tbsp\",\n      \"description\": \"\"\n    }\n  ],\n  \"allergic_content\": {\n    \"gluten\": \"May contain traces if using contaminated equipment\",\n    \"nuts\": \"May contain traces if using contaminated equipment\"\n  },\n  \"serving\": {\n    \"size\": 1,\n    \"unit\": \"serving\"\n  },\n  \"cooking_steps\": [\n    \"Boil quinoa in water until tender (about 15 minutes).\",\n    \"In a bowl, combine the cooked quinoa, chopped amaranth leaves, spinach, coriander, grated ginger, and spices.\",\n    \"Season with salt and lemon juice to taste. Mix well and serve.\"\n  ],\n  \"complementary_dishes\": [\n    \"Jain Vegetable Curry\",\n    \"Roti\",\n    \"Kachumber Salad\"\n  ],\n  \"nutritional_values_of_dish\": {\n    \"energy\": 250,\n    \"carbs\": 40,\n    \"proteins\": 10,\n    \"fats\": 5,\n    \"fibers\": 5,\n    \"thiamin\": 0.5,\n    \"riboflavin\": 0.6,\n    \"niacin\": 2,\n    \"vitamin_b5\": 1.5,\n    \"vitamin_b6\": 0.8,\n    \"vitamin_c\": 10,\n    \"biotin\": 5,\n    \"folate\": 50,\n    \"vitamin_a\": 500,\n    \"vitamin_d2\": 0,\n    \"vitamin_d3\": 0,\n    \"vitamin_k1\": 10,\n    \"vitamin_k2\": 0,\n    \"carotenoids\": 200,\n    \"vitamin_e\": 2,\n    \"calcium\": 50,\n    \"copper\": 0.5,\n    \"iron\": 3,\n    \"magnesium\": 100,\n    \"manganese\": 1.5,\n    \"potassium\": 250,\n    \"sodium\": 100,\n    \"zinc\": 2,\n    \"cholesterol\": 0,\n    \"sugar\": 2\n  }\n}\n```\n",
      ],
    },
    {
      "role": "user",
      "parts": [
        "You are a highly skilled culinary expert and food data analyst specializing in generating detailed dish information in JSON format. Your expertise includes correcting dish names (regardless of language or spelling variations) and presenting comprehensive details such as description, ingredients, cooking steps, and dietary information.\nInput Details:\n1.\tdish_name: Correct any spelling errors and identify the dish name, regardless of language.\n2.\tfood_category: Specifies whether the dish is Vegetarian or Non-vegetarian. \n                                    If eggs are included as an ingredient, classify the dish as non-vegetarian.\n3.\tis_jain: Indicates if the dish is Jain-compliant:\no\tIf \"jain\", exclude root vegetables (e.g., onions, garlic, potatoes) and other non-compliant ingredients.\no\tIf \"non-jain\", follow regular dietary guidelines for the selected food category.\nJSON Output Requirements:\n1.\tdish_name: Corrected name of the dish.\n2.\tdish_description: If provided, use this description directly to extract and must include all ingredients and cooking methods. Otherwise, A description to be generated between 20 to 200 characters highlighting main ingredients, flavor profile, and preparation style. Avoid excessive special characters.\n3.\tcuisine_category:\no\tcontinental_region: Validate against predefined regions (e.g., Asia, Europe, North America).\no\tspecific_cuisine: Match predefined cuisines within the selected region.\no\tsubcategory: Validate subcategories under the cuisine (e.g., \"North Indian\" for Indian cuisine).\n4.\ttiming_category: Select applicable options:\no\tBreakfast, Lunch, Snack, Dinner, Brunch, Midnight Snack\no\tUse: \"timing_category\": [\"__\"] for a single category or multiple options.\n5.\tmeal_category: Must select one options from these but should be in list:\no\tStarter, Soup, Salad, Main Course, Side Dish, Dessert, Drink, Snack\n6.\tcooking_method: If the description includes cooking methods, extract the primary method from it.\nIf the description does not include methods, extract them from the provided cooking steps.\nIf both are unavailable or inconclusive, infer a generic cooking method using an LLM. But you have to choose one or more methods from below list:\no\tBoiling, Steaming, Microwaving, Baking, Grilling, Frying, Sautéing, Pressure Cooking, Slow Cooking\n7.\tcooking_time: Provide time in standard format (e.g., \"45 minutes\") and validate against these ranges:\no\tQuick Cook: Under 30 minutes\no\tMedium Cook: 30–60 minutes\no\tLong Cook: 1–3 hours\no\tExtended Cook: Over 3 hours\n8.\tcooking_temperature: Provide in °C or °F, ensuring values are within valid ranges (e.g., 50°C–500°C). Convert Fahrenheit to Celsius if necessary. It must be in °C, for example 20 °C.\n9.\tingredients: You must have to take name of ingredients food_names.txt. A detailed list of ingredients including:\no\tname: Standardized English name.  \no\tquantity: Needed as per dish but it must be in number.\no\tunit: g (grams) or ml (milliliters), and There must not be in any other units if there is in then convert it into g (grams) or ml (milliliters) from non metrics too. If unit is in pieces the convert into exact gm or ml with respect to corresponding package. If any dish contains bread or pav or bun include it in ingredients and take it's unit as grams \"g\". Make sure not to use pieces, number , nos etc. in any of the ingredients use grams \"g\" for all solid ingredients and for liquid ingredients use \"ml\" and make sure for salt and pepper too you take it in grams \"g\".\no\tWhen including eggs as an ingredient, ensure the quantity is provided in grams. Assume that one egg weighs 40 grams, and if the quantity is given in pieces, multiply the number of pieces by 40 to convert it into grams.\no\tdescription: Ingredient state (e.g., \"chopped,\" \"boiled\").\nExample:\n{\n\"name\": \"Rice\",\n\"quantity\": \"50\",\n\"unit\": \"g\",\n\"description\": \"chopped\"\n}\n10.\tallergic_content: Leave this field empty. \n11.\tserving: Calculate serving size based on ingredient quantities. Consolidate into grams or milliliters. Example:\n{\n  \"size\": \" \",\n  \"unit\": \"g\"\n}\n12.\tcooking_steps: Provide detailed, step-by-step cooking instructions. Example:\n[\n  \"1. Rinse rice and moong dal thoroughly.\",\n  \"2. Combine rice and dal with water in a pan and bring to a boil.\",\n  \"3. Heat ghee in another pan and sauté spices.\",\n  \"4. Mix the spice mixture into the cooked khichdi and stir well.\"\n]\n13. complementary_dishes : Find out complementary dishes from \"dish_description\" or \"dish_name\". I want complementary dishes in list format.\nConsider this as the End of Input and Now all the things will be considered as Final output.(FO)\n\n\nKey Notes:\n•\tEnsure the dish details are tailored to the inputs (dish_name, food_category, and is_jain).\n•\tValidate all inputs and ensure accuracy in the generated JSON.\n•\tI only want json object in response nothing else.\n•\tI only want \"unit\" in g or ml in ingredients.\n•      If I have not give you food_category, and is_jain parameters then you generate it.\n•      In cooking_temperature says Room temperature but it must compulsory show number related to cooking temperature in Celsius. \n•      Ingredient names must be pulled directly from the provided ingredient database text file.\n•      Use oil is required use vegetable oil by default. \n•      Must generate \"nutritional_values_of_dish\" values. \n\n14. nutritional_values_of_dish : You consider your self as an expert nutrition value deriver. Provide details of below list nutrient details with specified units (in case you didn't find unit exact match- You have to convert those figures with accordance of standard convertor but the final output must be in given units only )\nFor calculating the nutrients values Strictly consider 200gm as serving sizes.\nYou have to consider Final output (FO) as the input for this calculation and perform the calculation with consideration of Cooking style , Temperature and other factors you may include. \nThe raw food database must be used from USDA database, Nothing else. The link for that database is : https://fdc.nal.usda.gov/.\nEnsure 500% accuracy in your result.   \nThe list of Nutrient with unit starts from here.\n    \"energy\": in kcal,\n    \"carbs\": in gram,\n    \"proteins\": in gram,\n    \"fats\": in gram,\n    \"fibers\": in gram,\n    \"thiamin\": in milligram,\n    \"riboflavin\": in milligram,\n    \"niacin\": in milligram,\n    \"vitamin_b5\": in milligram,\n    \"vitamin_b6\": in milligram,\n    \"vitamin_c\": in u milligram,\n    \"biotin\": in u milligram,\n    \"folate\": in u milligram,\n    \"vitamin_a\": in u milligram,\n    \"vitamin_d2\": in u milligram,\n    \"vitamin_d3\": in u milligram,\n    \"vitamin_k1\": in u milligram,\n    \"vitamin_k2\": in u milligram,\n    \"carotenoids\": in u milligram,\n    \"vitamin_e\": in milligram,\n    \"calcium\": in milligram,\n    \"copper\": in milligram,\n    \"iron\": in milligram,\n    \"magnesium\": in milligram,\n    \"manganese\": in milligram,\n    \"potassium\": in milligram,\n    \"sodium\": in milligram,\n    \"zinc\": in milligram\n  }",
      ],
    },
    {
      "role": "model",
      "parts": [
        "```json\n{\n  \"dish_name\": \"Jain Spiced Quinoa Salad\",\n  \"dish_description\": \"A flavorful and healthy salad with quinoa, mixed greens, and Jain-friendly spices.  Light and refreshing.\",\n  \"cuisine_category\": {\n    \"continental_region\": \"Asia\",\n    \"specific_cuisine\": \"Indian-inspired\",\n    \"subcategory\": \"Salad\"\n  },\n  \"timing_category\": [\n    \"Lunch\",\n    \"Dinner\"\n  ],\n  \"meal_category\": [\n    \"Salad\"\n  ],\n  \"food_category\": \"Vegetarian\",\n  \"is_jain\": \"jain\",\n  \"cooking_method\": [\n    \"Boiling\",\n    \"Mixing\"\n  ],\n  \"cooking_time\": \"20 minutes\",\n  \"cooking_temperature\": \"100°C\",\n  \"ingredients\": [\n    {\n      \"name\": \"Quinoa\",\n      \"quantity\": 100,\n      \"unit\": \"g\",\n      \"description\": \"rinsed\"\n    },\n    {\n      \"name\": \"Water\",\n      \"quantity\": 150,\n      \"unit\": \"ml\",\n      \"description\": \"for boiling\"\n    },\n    {\n      \"name\": \"Amaranth leaves, green\",\n      \"quantity\": 50,\n      \"unit\": \"g\",\n      \"description\": \"chopped\"\n    },\n    {\n      \"name\": \"Spinach\",\n      \"quantity\": 50,\n      \"unit\": \"g\",\n      \"description\": \"chopped\"\n    },\n    {\n      \"name\": \"Coriander leaves\",\n      \"quantity\": 25,\n      \"unit\": \"g\",\n      \"description\": \"chopped\"\n    },\n    {\n      \"name\": \"Ginger, fresh\",\n      \"quantity\": 5,\n      \"unit\": \"g\",\n      \"description\": \"grated\"\n    },\n    {\n      \"name\": \"Cardamom, green\",\n      \"quantity\": 1,\n      \"unit\": \"g\",\n      \"description\": \"ground\"\n    },\n    {\n      \"name\": \"Cumin seeds\",\n      \"quantity\": 2.5,\n      \"unit\": \"g\",\n      \"description\": \"ground\"\n    },\n    {\n      \"name\": \"Turmeric powder\",\n      \"quantity\": 1.25,\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Salt\",\n      \"quantity\": 2,\n      \"unit\": \"g\",\n      \"description\": \"\"\n    },\n    {\n      \"name\": \"Lemon juice\",\n      \"quantity\": 15,\n      \"unit\": \"ml\",\n      \"description\": \"\"\n    },\n        {\n      \"name\": \"Vegetable oil\",\n      \"quantity\": 5,\n      \"unit\": \"ml\",\n      \"description\": \"\"\n    }\n  ],\n  \"allergic_content\": {},\n  \"serving\": {\n    \"size\": 200,\n    \"unit\": \"g\"\n  },\n  \"cooking_steps\": [\n    \"Boil quinoa in water until tender (about 15 minutes).\",\n    \"In a bowl, combine the cooked quinoa, chopped amaranth leaves, spinach, coriander, grated ginger, and spices.\",\n    \"Season with salt and lemon juice to taste. Mix well and serve.\"\n  ],\n  \"complementary_dishes\": [\n    \"Jain Vegetable Curry\",\n    \"Roti\",\n    \"Kachumber Salad\"\n  ],\n  \"nutritional_values_of_dish\": {\n    \"energy\": 380,\n    \"carbs\": 70,\n    \"proteins\": 15,\n    \"fats\": 10,\n    \"fibers\": 7,\n    \"thiamin\": 0.7,\n    \"riboflavin\": 0.9,\n    \"niacin\": 4,\n    \"vitamin_b5\": 2.8,\n    \"vitamin_b6\": 1.4,\n    \"vitamin_c\": 180,\n    \"biotin\": 8,\n    \"folate\": 90,\n    \"vitamin_a\": 900,\n    \"vitamin_d2\": 0,\n    \"vitamin_d3\": 0,\n    \"vitamin_k1\": 18,\n    \"vitamin_k2\": 0,\n    \"carotenoids\": 360,\n    \"vitamin_e\": 3.5,\n    \"calcium\": 90,\n    \"copper\": 0.9,\n    \"iron\": 5,\n    \"magnesium\": 180,\n    \"manganese\": 2.8,\n    \"potassium\": 450,\n    \"sodium\": 200,\n    \"zinc\": 3.5\n  }\n}\n```\n",
      ],
    },
  ]
)

# system_instruction = """
# You are a highly skilled culinary expert and food data analyst with extensive experience in generating detailed dish information in JSON format. Your specialty lies in correcting dish names regardless of language or spelling variations and presenting comprehensive details about the dish, including its description, ingredients, cooking steps, and any relevant dietary information. Your task is to generate a JSON object for the dish based on the provided inputs: dish_name, food_category, and is_jain. The food_category determines whether the dish is vegetarian or non-vegetarian. Ensure the ingredients and description match this category. The is_jain input specifies whether the dish is Jain-compliant. If is_jain is "jain," exclude root vegetables (e.g., onions, garlic, potatoes, etc.) and any ingredients not allowed in Jain cuisine. If is_jain is "non-jain," the dish can follow the regular dietary guidelines for the selected food category.

# Include the following details in your output:

# {
#   "dish_name": "__",
#   "dish_description": "__",
#   "cuisine_category": {
#     "continental_region": "__",
#     "specific_cuisine": "__",
#     "subcategory": "__"
#   },
#   "timing_category": [
#     "__"
#   ],
#   "meal_category": [
#     "__"
#   ],
#   "food_category": "__",
#   "cooking_method": [
#     "__"
#   ],
#   "cooking_time": "__",
#   "cooking_temperature": "__",
#   "ingredients": [
#     {
#       "name": "__",
#       "quantity": "__",
#       "unit": "__",
#       "description": "__"
#     },
#     {
#       "name": "__",
#       "quantity": "__",
#       "unit": "__",
#       "description": "__"
#     },
#     {
#       "name": "__",
#       "quantity": "__",
#       "unit": "__",
#       "description": "__"
#     }
#   ],
#   "allergic_content": {},
#   "serving": {
#       "size": "__",
#       "unit": "__"
#     },
#   "cooking_steps": [
#     "__",
#     "__",
#     "__"
#   ]
# }

# Ensure the `serving` field includes the following:
# 1. `full_serving`: Representing the provided full serving size and its unit.
# 2. `half_serving`: Automatically calculated by dividing the `full_serving` size by 2 while retaining the same unit.
# """)

def generate_dish_from_model1( dish_name, chat_session,persons, price=None, is_price=False, desc=None, is_desc=False):

    price = float(price) if is_price else 399.00
    print(f"final price is:{price}")
  
    logger.debug("Calling AI model...")

    
    if is_desc:
        logger.info("Using provided description as 'is_desc' is True.")
        try:
            response = chat_session.send_message(f"{dish_name}, {desc}")
            ai_data = json.loads(response.text)
            ai_data["dish_description"] = desc

        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to decode AI response: {str(e)}. Using fallback values.")
            ai_data = {"dish_name": dish_name, "dish_description": desc}
    else:
        logger.info("'is_desc' is False. Generating description using AI.")
        try:
            print("Dish generation")
            response = chat_session.send_message(f"{dish_name}")
            ai_data = json.loads(response.text)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to decode AI response: {str(e)}. Using default description.")

    servings = sum(float(ingredient["quantity"]) for ingredient in ai_data["ingredients"])
    
    new_serving_size = 200 * persons

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
                print(ingredient['swap_items'])
                ingredient["is_swappable"] = True
    print(f"ingredients_list: {ingredients_list}")   


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
    print("model 1 comepleted")
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

    print("as per category lets perform min max value")
    print(ai_data)
    
    updated_ai_data = adjust_quantities_with_min_max(ai_data)
    
    return updated_ai_data
