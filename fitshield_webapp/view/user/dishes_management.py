from asyncio.log import logger
from datetime import datetime
import json
import logging
import os
from turtle import update
from config.connection import db
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

# from fitshield_webapp.AI.AIModel.User.get_nutrients import combine_tags_into_dishes, fetch_dishes_by_restro_id, fetch_user_data, organize_dishes
from fitshield.settings import  MIN_DISH_LEVEL
from fitshield_webapp.AI.AIModel.User.get_personalize_dish import default_goal_dishes
from fitshield_webapp.AI.AIModel.User.new_goal_personalize_dish import fetch_dishes_by_restro_id, live_goal_dishes, calculate_nutrient_percentages
# from fitshield_webapp.utils.calculation import calculate_nutrient_percentages
from fitshield_webapp.view.restro.save_json import save_json_to_file

logging.basicConfig(filename='dish_matching.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@csrf_exempt
def get_restaurant_categories(request):
    if request.method == "GET":
        try:
            restro_id = request.GET.get("restro_id")
            is_veg_filter = request.GET.get("is_veg")  # Get is_veg from query params

            # Convert is_veg_filter to a boolean (default: None, meaning no filter)
            if is_veg_filter is not None:
                is_veg_filter = is_veg_filter.lower() == "true"

            # Validate input
            if not restro_id:
                return JsonResponse({"message": "restro_id is required."}, status=400)

            # Access the RestaurantMenuData collection
            restaurant_collection = db["RestaurantMenuData"]

            # Fetch restaurant details by restro_id
            restaurant = restaurant_collection.find_one({"_id": restro_id})
            if not restaurant:
                return JsonResponse({"message": "Restaurant not found."}, status=404)

            # Fetch the menu data from the restaurant document
            menu = restaurant.get("menu", [])
            if not menu:
                return JsonResponse([], safe=False)  # Return an empty list if no menu is found

            # Initialize a dictionary to count categories
            category_counts = {}

            # Iterate through dishes in the menu and count categories
            for dish in menu:
                if dish.get("is_verified") == True and dish.get("is_dish_approved") == True and dish.get("is_out_of_stock") == False:  # Only include verified and in-stock dishes
                    food_category = dish.get("food_category", "").lower()  # Get food category (e.g., "Vegetarian", "Non-vegetarian")

                    # Determine if dish should be included based on is_veg_filter
                    if is_veg_filter is True and food_category != "vegetarian":
                        continue  # Skip non-vegetarian dishes if filtering for veg-only

                    meal_categories = dish.get("meal_category", [])  # Fetch meal categories for the dish
                    for category in meal_categories:
                        category_counts[category] = category_counts.get(category, 0) + 1

            # Transform the dictionary into a list of objects
            category_list = [{"category": category, "count": count} for category, count in category_counts.items()]

            # Return the list of categories and counts
            return JsonResponse(category_list, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON format."}, status=400)
        except Exception as e:
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)

@csrf_exempt
def get_restro_data(request):
    if request.method == "GET":
        try:
            # Get the restro_id from query parameters
            restro_id = request.GET.get("restro_id", "").strip()

            # Validate input
            if not restro_id:
                return JsonResponse({"message": "restro_id is required."}, status=400)

            # Access the RestroData collection
            restrodata_collection = db["RestroData"]

            # Fetch the restaurant data by restro_id
            restro_data = restrodata_collection.find_one({"_id": restro_id}, {"_id": 0})  # Exclude MongoDB's _id field

            if not restro_data:
                return JsonResponse({"message": "Restaurant not found."}, status=404)

            # Add the restro_id to the response data
            restro_data["restro_id"] = restro_id

            # Return restaurant data
            return JsonResponse(restro_data, safe=False)

        except Exception as e:
            return JsonResponse({"message": "An unexpected error occurred.", "details": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)
    
@csrf_exempt
def get_restaurant_menu(request):
    if request.method == "GET":
        try:
            # Get query parameters
            restro_id = request.GET.get("restro_id", "").strip()
            user_id = request.GET.get("user_id", "").strip()
            is_default_goal = request.GET.get("is_default_goal", "").strip()
            is_veg = request.GET.get("is_veg", "").strip().lower()

            # Ensure is_personalized is properly converted to Boolean
            is_personalized = request.GET.get("is_personalized", "false")
            if isinstance(is_personalized, str):  
                is_personalized = is_personalized.strip().lower() == "true"

            folder_name = "dishes_output"

            # Create the output folder if it doesn't exist
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)

            # Validate restro_id
            if not restro_id:
                return JsonResponse({"message": "restro_id is required."}, status=400)

            # Access the RestaurantMenuData collection
            menu_collection = db["RestaurantMenuData"]
            menu_data = menu_collection.find_one({"_id": restro_id})
            filtered_dishes = []

            if menu_data and "menu" in menu_data:
                filtered_dishes = menu_data["menu"]  # Set filtered_dishes with menu items

                if MIN_DISH_LEVEL == "verified":
                    filtered_dishes = [
                        dish for dish in filtered_dishes 
                        if dish.get("is_verified") == True
                    ]
                elif MIN_DISH_LEVEL == "unverified":
                    filtered_dishes = [dish for dish in filtered_dishes]
                else:
                    return JsonResponse({"message": "Menu not found for the given restro_id."}, status=404)

                is_veg = request.GET.get("is_veg", "").strip().lower()
                if is_veg == "true":
                    filtered_dishes = [
                        dish for dish in filtered_dishes 
                        if dish.get("food_category") == "Vegetarian"
                    ]

            # Fetch user allergies from UserData collection
            user_data_collection = db["UserData"]
            user_data = user_data_collection.find_one({"_id": user_id})
            
            user_allergies = user_data.get("allergies", []) if user_data else []

            # 1) Existing allergy check (allergic_content)
            if user_allergies:
                filtered_dishes = [
                    dish for dish in filtered_dishes
                    if not any(
                        allergen in user_allergies 
                        for allergen in dish.get("allergic_content", [])
                    )
                ]

                def has_variant_allergy(dish, user_allergies):
                    user_allergies_lower = [a.lower() for a in user_allergies]
                    dish_variants = dish.get("dish_variants", {})
                    for variant_name, variant_data in dish_variants.items():
                        if isinstance(variant_data, dict):
                            for portion_name, portion_info in variant_data.items():
                                if isinstance(portion_info, dict):
                                    variant_ingredients = portion_info.get("ingredients", [])
                                    for ing in variant_ingredients:
                                        if isinstance(ing, dict):
                                            ing_name = ing.get("name", "").lower()
                                            for allergy in user_allergies_lower:
                                                if allergy in ing_name:
                                                    return True
                                        elif isinstance(ing, str):
                                            ing_lower = ing.lower()
                                            for allergy in user_allergies_lower:
                                                if allergy in ing_lower:
                                                    return True
                    return False

                filtered_dishes = [
                    dish for dish in filtered_dishes
                    if not has_variant_allergy(dish, user_allergies)
                ]

            if user_allergies:
                # Load allergen data from the provided file path
                allergen_data_path = os.path.join("fitshield_webapp", "AI", "AIModel", "User", "allergen_data.json")
                if os.path.exists(allergen_data_path):
                    with open(allergen_data_path, "r", encoding="utf-8") as f:
                        allergen_data = json.load(f)
                else:
                    allergen_data = []

                # Build a dictionary: category -> list of synonyms
                allergy_map = {}
                for entry in allergen_data:
                    cat = entry["Allergy_category"].strip().lower()
                    synonyms_list = [s.strip().lower() for s in entry["Ingredient_Name"].split(",")]
                    allergy_map[cat] = synonyms_list

                # Gather all synonyms for user's allergies
                all_synonyms = set()
                for user_allergy in user_allergies:
                    ua_lower = user_allergy.lower()
                    if ua_lower in allergy_map:
                        all_synonyms.update(allergy_map[ua_lower])
                    else:
                        for cat_key, syn_list in allergy_map.items():
                            if ua_lower in syn_list:
                                all_synonyms.update(syn_list)

                # Function to check partial match for any synonym in dish texts
                def dish_has_synonym(dish, synonyms_set):
                    def contains_synonym(text):
                        text_lower = text.lower()
                        return any(syn in text_lower for syn in synonyms_set)
                    # Check allergic_content
                    for ac in dish.get("allergic_content", []):
                        if contains_synonym(ac):
                            return True
                    # Check dish_variants ingredients
                    dish_variants = dish.get("dish_variants", {})
                    for variant_name, variant_data in dish_variants.items():
                        if isinstance(variant_data, dict):
                            for portion_name, portion_info in variant_data.items():
                                if isinstance(portion_info, dict):
                                    var_ing = portion_info.get("ingredients", [])
                                    for v_ing in var_ing:
                                        if isinstance(v_ing, dict):
                                            v_ing_name = v_ing.get("name", "")
                                            if contains_synonym(v_ing_name):
                                                return True
                                        elif isinstance(v_ing, str):
                                            if contains_synonym(v_ing):
                                                return True
                    return False

                if all_synonyms:
                    filtered_dishes = [
                        dish for dish in filtered_dishes
                        if not dish_has_synonym(dish, all_synonyms)
                    ]

            # ------------------------------------------------------------------
            # (3) REMAINDER OF YOUR ORIGINAL CODE (UNCHANGED)
            # ------------------------------------------------------------------
            if menu_data:
                menu_data["menu"] = filtered_dishes

            grouped_menu = {}
            for dish in menu_data.get("menu", []):  # Assuming dishes are stored under "menu"
                if dish.get("is_out_of_stock") or dish.get("is_dish_approved") ==  False or dish.get("is_verified") == False:  # Skip the dish if out of stock
                    continue
                meal_categories = dish.get("meal_category", ["Uncategorized"])
                for category in meal_categories:
                    if category not in grouped_menu:
                        grouped_menu[category] = []
                    grouped_menu[category].append(dish)

            best_match_dishes = []
            if is_personalized:
                if is_default_goal.lower() == "true":
                    dishes = default_goal_dishes(restro_id, user_id)
                else:
                    dishes = live_goal_dishes(restro_id, user_id)

                output_file = os.path.join(folder_name, "personalized_menu.json")
                with open(output_file, "w") as json_file:
                    json.dump(dishes, json_file, indent=4)

                if not dishes:
                    dishes = default_goal_dishes(restro_id, user_id)
                if not dishes:
                    return JsonResponse({"message": "Error organizing personalized dishes."}, status=500)

                for category, category_dishes in grouped_menu.items():
                    for dish in category_dishes:
                        found_match = False
                        for personalized_category in dishes:
                            for personalized_dish in personalized_category["dishes"]:
                                if dish["dish_name"] == personalized_dish["dish_name"]:
                                    dish["match"] = personalized_dish.get("match", "No Match")
                                    if dish["match"] == "Best Match":
                                        best_match_dishes.append(dish)
                                    found_match = True
                        if not found_match:
                            dish["match"] = "No Match"

            formatted_menu = []
            if is_personalized:
                formatted_menu.append({
                    "category": "Best Match",
                    "dishes": best_match_dishes if best_match_dishes else []
                })

            formatted_menu.extend(
                {"category": category, "dishes": dishes}
                for category, dishes in grouped_menu.items()
                if dishes
            )

            return JsonResponse(formatted_menu, safe=False)

        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}", exc_info=True)
            return JsonResponse({"message": "An unexpected error occurred.", "details": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)
    
@csrf_exempt
def calc_macros(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST is allowed"}, status=405)

    try:
        body = json.loads(request.body)
    except:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)
    
    user_id = body.get("user_id")
    if not user_id:
        return JsonResponse({"error": "Missing user_id"}, status=400)

    carbs_g   = body.get("carbs_g")
    protein_g = body.get("protein_g")
    fats_g    = body.get("fats_g")
    fiber_g   = body.get("fiber_g", 0)
    
    # carbs_g = float(carbs_g)
    # protein_g = float(protein_g)
    # fats_g = float(fats_g)
    # fiber_g = float(fiber_g)
    

    daily_kcal = body.get("daily_kcal")

    user_data_collection = db["UserData"]  

    has_4_macros = (carbs_g is not None and protein_g is not None and fats_g is not None)

    if has_4_macros:
        total_cals = (carbs_g*4) + (protein_g*4) + (fats_g*9) + (fiber_g*2)
        if total_cals <= 0:
            return JsonResponse({"error": "Invalid macros, total=0"}, status=400)

        # Store values with two decimal points
        macro_info = {
            "total_kcal": {"value": round(total_cals, 2), "unit": "kcal"},
            "protein_g": {"value": round(protein_g, 2), "unit": "g"},
            "carbs_g": {"value": round(carbs_g, 2), "unit": "g"},
            "fats_g": {"value": round(fats_g, 2), "unit": "g"},
            "fiber_g": {"value": round(fiber_g, 2), "unit": "g"}
        }

    else:
        if daily_kcal is None:
            return JsonResponse({"error": "Must provide daily_kcal or 4 macros."}, status=400)

        # Fetch user doc from DB
        user_doc = user_data_collection.find_one({"_id": user_id})
        # print(user_doc)
        if not user_doc:
            return JsonResponse({"error": f"No user found with _id={user_id}"}, status=404)

        # We'll get age, gender, goal, weight from doc
        age    = user_doc.get("age", 25)       # default 25 if missing
        gender = user_doc.get("gender", "Male")
        goal   = user_doc.get("goal", "Muscle Gain")


        weight_obj = user_doc.get("weight", {"value": 70.0})  # default to {"value": 70.0} if missing

        # Extract weight value (convert to float) - just the numeric part
        if isinstance(weight_obj, dict) and 'value' in weight_obj:
            weight_val = float(weight_obj['value'])  # Convert the weight value to float (e.g. 23.59)
        else:
            weight_val = 70.0  # Default weight if not found or in unexpected format
      

        # Now call snippet logic
        # print("before snippet")
        macros = calculate_nutrient_percentages(daily_kcal, age, gender, goal, weight_val)
        tdee = macros["tdee"]
        p = macros["p"]
        c = macros["c"]
        fa = macros["fa"]
        fiber = macros["fiber"]
        # print("after snippet")

        macro_info = {
            "total_kcal": {"value": round(tdee, 2), "unit": "kcal"},
            "protein_g": {"value": round(p, 2), "unit": "g"},
            "carbs_g": {"value": round(c, 2), "unit": "g"},
            "fats_g": {"value": round(fa, 2), "unit": "g"},
            "fiber_g": {"value": round(fiber, 2), "unit": "g"}
        }
        # print(f"done done: {macro_info}")
    # Store in DB
    filter = {"_id": user_id}
    update = {
        "$set": {
            "goals.live_goal.kcal": macro_info["total_kcal"],
            "goals.live_goal.nutrients.protein": macro_info["protein_g"],
            "goals.live_goal.nutrients.carbs":   macro_info["carbs_g"],
            "goals.live_goal.nutrients.fats":    macro_info["fats_g"],
            "goals.live_goal.nutrients.fiber":   macro_info["fiber_g"],
            "updated_at": datetime.utcnow().isoformat()
        }
    }
    res = user_data_collection.update_one(filter, update)

    return JsonResponse({
        "message": "Macros computed & stored successfully.",
        "macro_info": macro_info
    }, status=200)

def get_user_ordered_dish_names(user_id, cart_id):

    ordered_dish_names = set()
    cart_collection=db['Cart']
    #individual carts
    individual_carts = list(cart_collection.find({"_id": cart_id}))
    for cart in individual_carts:
        for dish in cart.get("ordered_dishes", []):
            name = dish.get("name")
            if name:
                ordered_dish_names.add(name.lower())
                
    # group carts
    group_carts = list(cart_collection.find({"group_id": {"$ne": None}}))
    for cart in group_carts:
        for entry in cart.get("dishes", []):
            if entry.get("added_by") == user_id:
                for dish in entry.get("dishes", []):
                    name = dish.get("name")
                    if name:
                        ordered_dish_names.add(name.lower())
    return ordered_dish_names


@csrf_exempt
def get_recommended_dishes(request):
    if request.method == "GET":
        try:
            restro_id = request.GET.get("restro_id")
            user_id = request.GET.get("user_id")
            is_personalize = request.GET.get("is_personalize", "false").lower() == "true"
            is_default_goal = request.GET.get("is_default_goal", "").strip().lower()
            cart_id = request.GET.get("cart_id", None)

            if not restro_id or not user_id:
                return JsonResponse({"message": "restro_id and user_id are required."}, status=400)
            
            # Determine the type of recommendation
            if is_personalize:
                if is_default_goal == "true":
                    recommendations = default_goal_dishes(restro_id, user_id)
                else:
                    recommendations = live_goal_dishes(restro_id, user_id)

                # final_dishes = [dish for dish in recommendations for dish in dish["dishes"]]
                final_dishes = [dish for category in recommendations for dish in category.get("dishes", [])] if recommendations else []

            else:
                menu_data = fetch_dishes_by_restro_id(restro_id)
                recommendations = []
                target_categories = ["beverage/drink", "snacks", "dessert"]
                for dish in menu_data:
                    print(dish)
                    categories = [cat.strip().lower() for cat in dish.get("meal_category", [])]
                    if any(cat in target_categories for cat in categories):
                        recommendations.append(dish)
                # final_dishes =  recommendations
                final_dishes = recommendations if recommendations else []

            print(final_dishes)
            # Exclude already ordered dishes
            ordered_dishes = get_user_ordered_dish_names(user_id, cart_id)
            
            final_dishes = [dish for dish in final_dishes if dish.get("dish_name", "").lower() not in ordered_dishes]

            return JsonResponse({"category": "recommendation", "dishes": final_dishes}, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON format."}, status=400)
        except Exception as e:
            logging.exception("Error in recommended_dishes_api")
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)



@csrf_exempt
def get_dishes_by_category(request):
    if request.method == "GET":
        try:
            # Get the required parameters from the request
            restro_id = request.GET.get("restro_id")
            if not restro_id:
                return JsonResponse({"message": "restro_id is required."}, status=400)

            # Define the target categories
            target_categories = ["snacks", "dessert", "beverage/drink"]
            recommendations = []
            
            collection = db["RestaurantMenuData"]  # Your collection name
            
            # Fetch the restaurant data by restro_id from MongoDB
            restaurant_data = collection.find_one({"_id": restro_id})
            if not restaurant_data:
                return JsonResponse({"message": "Restaurant not found."}, status=404)

            # Filter dishes based on the target categories
            for dish in restaurant_data['menu']:
                # Get the secondary categories of the dish
                dish_categories = [cat.strip().lower() for cat in dish.get('meal_category', [])]
                
                # Check if any of the target categories match
                if any(category in dish_categories for category in target_categories):
                    recommendations.append(dish)

            # If no recommendations found, return an empty response
            if not recommendations:
                return JsonResponse({"category": "recommendation", "dishes": []}, safe=False)

            # Return the filtered list of dishes as a JSON response
            return JsonResponse({"category": "recommendation", "dishes": recommendations}, safe=False)

        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON format."}, status=400)
        except Exception as e:
            logging.exception("Error in get_dishes_by_category API")
            return JsonResponse({"message": str(e)}, status=500)
    else:
        return JsonResponse({"message": "Invalid HTTP method. Use GET."}, status=405)

