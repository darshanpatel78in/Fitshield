from datetime import date, datetime
import json
import logging
import os

from django.http import JsonResponse
from config.connection import db
from fitshield.settings import MIN_DISH_LEVEL
from fitshield_webapp.view.restro.save_json import save_json_to_file
from .data import possibilities

menu_collection = db["RestaurantMenuData"]
user_data_collection = db["UserData"]

def get_selected_meal():
        current_hour = datetime.now().hour

        # Define meal time ranges (24-hour format)
        meal_times = {
            "Breakfast": (6, 11),   # 6:00 AM - 10:59 AM
            "Lunch": (11, 15),      # 11:00 AM - 2:59 PM
            "Snacks": (15, 18),     # 3:00 PM - 5:59 PM
            "Dinner": (18, 24),     # 6:00 PM - 12:00 PM
        }

        selected_meal = "   "  #if selected meal is not in time category
        for meal, (start, end) in meal_times.items():
            if start <= current_hour < end:
                selected_meal = meal
                break

        return selected_meal

def fetch_dishes_by_restro_id(restro_id):
    dishes = menu_collection.find_one({"_id": restro_id})
    if dishes:
        if MIN_DISH_LEVEL == "unverified":
            dishes["menu"] = [dish for dish in dishes["menu"]]
        elif MIN_DISH_LEVEL == "verified":
            dishes["menu"] = [dish for dish in dishes["menu"] if dish.get("is_verified") == True]
        # Apply the condition to exclude out-of-stock dishes
        dishes["menu"] = [dish for dish in dishes["menu"] if dish.get("is_out_of_stock") == False and dish.get("is_dish_approved") == True]
    else:
        return JsonResponse({"message": "Menu not found for the given restro_id."}, status=404)
    return dishes["menu"]

def fetch_user_data(user_id):
    User = user_data_collection.find_one({"_id": user_id})
    if not User:
        return None
    return User


def user_data_process(data):

    # Constants
    MACRO_CALORIES = {"carbs": 4, "protein": 4, "fats": 9}
    DAILY_FIBER = {"women": 25, "men": 38}
    TEMPERATURE_FACTORS = {
        "Cold (Below 10°C)": 1.2,
        "Moderately Cold (10°C to 18°C)": 1.07,
        "Neutral (18°C to 25°C)": 1.0,
        "Warm (25°C to 30°C)": 1.03,
        "Hot (Above 30°C)": 1.07,
        "Extremely Hot (Above 35°C)": 1.15,
    }
    ACTIVITY_FACTORS = {
        "Sedentary": 1.2,
        "Lightly active": 1.375,
        "Moderate": 1.55,
        "Very active": 1.725,
        "Super active": 1.9,
    }
    EXERCISE_FACTORS = {
        "No exercise": 0,
        "Light": 0.175,
        "Moderate": 0.35,
        "Heavy": 0.525,
        "Very heavy": 0.7,
    }
    # Map yoga types to exercise factors
    YOGA_FACTORS = {
        "None": 0,
        "Light": 0.175,
        "Moderate": 0.35,
        "Heavy": 0.525,
    }

    # Constants for Macronutrient Ratios
    MACRONUTRIENT_RATIOS = {
        "Standard": {
            "Muscle Gain": {
                "Male": {
                    "18-40": {"Carbs": (0.50, 0.55), "Proteins": (0.20, 0.25), "Fats": (0.20, 0.25), "Fiber": 38},
                    "40+": {"Carbs": (0.50, 0.55), "Proteins": (0.15, 0.20), "Fats": (0.25, 0.30), "Fiber": 38}
                },
                "Female": {
                    "18-40": {"Carbs": (0.50, 0.55), "Proteins": (0.20, 0.22), "Fats": (0.20, 0.25), "Fiber": 25},
                    "40+": {"Carbs": (0.50, 0.55), "Proteins": (0.15, 0.20), "Fats": (0.25, 0.30), "Fiber": 25}
                }
            },
            "Weight Loss": {
                "Male": {
                    "18-40": {"Carbs": (0.40, 0.45), "Proteins": (0.20, 0.25), "Fats": (0.30, 0.35), "Fiber": 38},
                    "40+": {"Carbs": (0.45, 0.50), "Proteins": (0.15, 0.20), "Fats": (0.30, 0.35), "Fiber": 38}
                },
                "Female": {
                    "18-40": {"Carbs": (0.40, 0.45), "Proteins": (0.20, 0.22), "Fats": (0.30, 0.35), "Fiber": 25},
                    "40+": {"Carbs": (0.45, 0.50), "Proteins": (0.15, 0.20), "Fats": (0.30, 0.35), "Fiber": 25}
                }
            },
            "Healthy Eating": {
                "Male": {
                    "18-40": {"Carbs": (0.55, 0.60), "Proteins": (0.10, 0.15), "Fats": (0.20, 0.25), "Fiber": 38},
                    "40+": {"Carbs": (0.50, 0.55), "Proteins": (0.10, 0.12), "Fats": (0.25, 0.30), "Fiber": 38}
                },
                "Female": {
                    "18-40": {"Carbs": (0.55, 0.60), "Proteins": (0.10, 0.15), "Fats": (0.20, 0.25), "Fiber": 25},
                    "40+": {"Carbs": (0.50, 0.55), "Proteins": (0.10, 0.12), "Fats": (0.25, 0.30), "Fiber": 25}
                }
            }
        },
        "Diabetic": {
            "Carbs": (0.45, 0.45),    # 45% fixed
            "Proteins": (0.2, 0.2),   # 20% fixed
            "Fats": (0.35, 0.35),     # 35% fixed
        }
    }

    # Fiber requirements (per meal based on gender)
    FIBER_REQUIREMENTS = {
        "Female": (6, 9),  # 6-9 grams per meal
        "Male": (10, 13),  # 10-13 grams per meal
        "Not prefer to say": (6, 13)
    }


    # Functions
    def calculate_bmr(weight, height, age, gender):
        if gender == "Male":
            return (10 * weight) + (6.25 * height) - (5 * age) + 5
        elif gender == "Female":
            return (10 * weight) + (6.25 * height) - (5 * age) - 161
        else:
            return (((10 * weight) + (6.25 * height) - (5 * age) + 5) + ((10 * weight) + (6.25 * height) - (5 * age) - 161)) / 2

    def calculate_tdee(bmr, temp_factor , activity_factor, exercise_factor, goal_factor):
        adjusted_bmr = bmr * temp_factor
        tdee1 = adjusted_bmr * activity_factor
        tdee2 = tdee1 + (exercise_factor * tdee1)
        tdee3 = tdee2 * goal_factor
        return tdee1, tdee2, tdee3

    # Function to distribute caloric intake across meals
    def calculate_meal_distribution(tdee3):
        # Meal percentage ranges
        meal_percentages = {
            "Breakfast": (0.2, 0.25),  # 20-25%
            "Lunch": (0.3, 0.35),     # 30-35%
            "Snacks": (0.1, 0.15),    # 10-15%
            "Dinner": (0.3, 0.35),    # 30-35%
        }

        # Calculate calorie ranges for each meal
        meal_calories = {}
        for meal, (low, high) in meal_percentages.items():
            low_calories = tdee3 * low
            high_calories = tdee3 * high
            meal_calories[meal] = (low_calories, high_calories)

        return meal_calories

    # Function to calculate fixed calories based on hunger index
    def calculate_fixed_calories(meal_distribution, hunger_level):
        fixed_calories = {}
        for meal, (low, high) in meal_distribution.items():
            if hunger_level == "Low":
                fixed_calories[meal] = low  # Lowest value
            elif hunger_level == "Normal":
                fixed_calories[meal] = (low + high) / 2  # Midpoint value
            elif hunger_level == "High":
                fixed_calories[meal] = high  # Highest value
        return fixed_calories

    def calculate_macronutrients(calories, profile_type, gender,goal_type,age_group):

        ratios = MACRONUTRIENT_RATIOS[profile_type][goal_type][gender][age_group]
        fiber_range = FIBER_REQUIREMENTS[gender]

        # Macronutrient calculations
        carb_kcal = (calories * ratios["Carbs"][0], calories * ratios["Carbs"][1])  # Carbs in kcal
        protein_kcal = (calories * ratios["Proteins"][0], calories * ratios["Proteins"][1])  # Protein in kcal
        fat_kcal = (calories * ratios["Fats"][0], calories * ratios["Fats"][1])  # Fats in kcal

        # Convert kcal to grams
        carbs_grams = [carb_kcal[0] / 4, carb_kcal[1] / 4]  # Carbs in grams
        proteins_grams = [protein_kcal[0] / 4, protein_kcal[1] / 4]  # Proteins in grams
        fats_grams = [fat_kcal[0] / 9, fat_kcal[1] / 9]  # Fats in grams
        fiber_grams = list(fiber_range)  # Convert fiber tuple to list
        carbs=(carbs_grams[1]+carbs_grams[0])/2
        protein=(protein_kcal[1]+protein_kcal[0])/2
        fats=()
        

        # Return formatted dictionary
        return {
            "Carbs (g)": carbs_grams,
            "Proteins (g)": proteins_grams,
            "Fats (g)": fats_grams,
            "Fiber (g)": fiber_grams,
        }


    def calculate_age(birth_date_str):
    # Parse the string to a date object
        birth_date = datetime.strptime(birth_date_str, "%d-%m-%Y").date()
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age

    # userinput
    country_code = data["mobile_number"]
    gender = data["gender"]
    weight = float(data.get("weight", {}).get("value", 0.0))
    height = float(data.get("height", {}).get("value", 0.0))
    weight_unit = data.get("weight", {}).get("unit", "kg")
    height_unit = data.get("height", {}).get("unit", "cm")
    dob = data["dob"]
    age = calculate_age(dob)
    temperature = "Neutral (18°C to 25°C)"

    daily_routine = data["life_routine"]

    # Activity Selection
    activity_type = data["gym_or_yoga"]
    selected_activity = None  # Track the specific activity selected

    if activity_type == "Gym":
        selected_activity = data["intensity"]
        activity_factor = EXERCISE_FACTORS[selected_activity]
    elif activity_type == "Yoga":
        selected_activity = data["intensity"]
        activity_factor = YOGA_FACTORS[selected_activity]
    else:
        activity_factor = 0


    # Goal Consideration Inputs
    goal_subcategory = None  # To store sub-goal details

    goal = data["goal"]

    # Sub-options for Muscle Gain and Weight Loss
    if goal == "Muscle Gain":
        goal_subcategory = "Moderate Muscle Gain (Balanced Approach)"
        muscle_gain_factors = {
            "Lean Muscle Gain (Slow and Controlled)": 1.075,
            "Moderate Muscle Gain (Balanced Approach)": 1.175,
            "Aggressive Muscle Gain (Rapid Bulking)": 1.275,
        }
        goal_factor = muscle_gain_factors[goal_subcategory]

    elif goal == "Weight Loss":
        goal_subcategory = "Moderate Weight Loss (Balanced Approach)"
        fat_loss_factors = {
            "Mild Weight Loss (Slow and Sustainable)": 0.925,
            "Moderate Weight Loss (Balanced Approach)": 0.825,
            "Aggressive Weight Loss (Rapid Results)": 0.725,
        }
        goal_factor = fat_loss_factors[goal_subcategory]
    else:
        goal_factor = 1.0

    hunger_level = data["hunger_level"]

    # Calculate BMR
    bmr = calculate_bmr(weight, height, age, gender)


    # Adjusted TDEE
    tdee1, tdee2, tdee3 = calculate_tdee(
        bmr,
        TEMPERATURE_FACTORS[temperature],
        ACTIVITY_FACTORS[daily_routine],
        activity_factor,
        goal_factor
    )

    # Distribute calories for TDEE3
    meal_distribution = calculate_meal_distribution(tdee3)
    fixed_meal_calories = calculate_fixed_calories(meal_distribution, hunger_level)

    # Display the result for the selected meal category
    selected_meal = get_selected_meal()

    profile_type = "Standard"

    # Get calories for the selected meal category (from previous step)
    selected_meal_calories = fixed_meal_calories[selected_meal]  # Calories for selected meal

    if 18 <= age <= 40:
        age_group = "18-40"
    elif age > 40:
        age_group = "40+"
    else:
        age_group = "18-40"

    # Calculate macronutrients
    macronutrients = calculate_macronutrients(selected_meal_calories, profile_type, gender, goal,age_group)

    # Display results
    # User Data JSON
    user_input = {
        "Country Code": country_code,
        "Gender": gender,
        "Weight (kg)": weight,
        "Height (cm)": height,
        "Age": age,
        "Temperature": temperature,
        "daily_routine": daily_routine,
        "Activity Type": activity_type,
        "Activity Sub-Category": selected_activity if activity_type != "None" else "None",
        "Goal": goal,
        "Goal Sub-Category": goal_subcategory if goal_subcategory else "None",
        "Hunger Level": hunger_level,
        "Selected Meal": selected_meal,
        "BMR (kcal/day)": bmr,
        "TDEE (kcal/day)": {"Activity Level": tdee1, "Exercise/Yoga Adjusted": tdee2, "Goal Adjusted": tdee3},
        "Hunger Level": hunger_level,
        "Fixed Calories": fixed_meal_calories[selected_meal],
        "profile_type": profile_type
    }

    return user_input

def calculate_maida_percentage(ingredients, serving_size):
    logging.debug(f"let's calculate_maida_percentage : ingredients = {ingredients}, serving_size = {serving_size}")

    maida_quantity = 0
    total_quantity = 0

    for ingredient in ingredients:
        quantity = float(ingredient.get("quantity", 0))
        total_quantity += quantity
        if "maida" in ingredient["name"].lower() or "refined flour" in ingredient["name"].lower():
            maida_quantity += quantity

    if serving_size > 0:
        return (maida_quantity / serving_size) * 100
    elif total_quantity > 0:
        return (maida_quantity / total_quantity) * 100
    return 0

def find_combination(protein_category, carbs_category, fats_category):
    logging.debug(f"find combinations: protein_category = {protein_category}, carbs_category = {carbs_category}, fats_category = {fats_category}")
    for possibility in possibilities:
        if (possibility["Protein"] == protein_category and
            possibility["Carbs"] == carbs_category and
            possibility["Fats"] == fats_category):
            return {"End Result": possibility["End Result"]}
    return {"End Result": "Unknown"}

def find_range(value, ranges):
    logging.debug(f"let's find_range : value = {value}, ranges = {ranges}")
    for tag_name, range_values in ranges.items():
        if isinstance(range_values[0], list):  # For ranges like Moderate or Avoid
            for sub_range in range_values:
                if sub_range[0] <= value <= sub_range[1]:
                    return tag_name
        elif range_values[0] <= value <= range_values[1]:  # For Best ranges
            return tag_name
    return "Avoid"


def apply_conditions(dish_name, end_result, protein_percentage, carbs_percentage, fats_percentage, sugar_percentage, sodium_per_100g, cholesterol_per_100g, maida_percentage):
    # Apply Protein Overrule condition
    logging.debug(f"let's apply conditions : dish_name = {dish_name}, end_result = {end_result}, protein_percentage = {protein_percentage}, carbs_percentage = {carbs_percentage}, fats_percentage = {fats_percentage}, sugar_percentage = {sugar_percentage}, sodium_per_100g = {sodium_per_100g}")

    if (
        end_result["End Result"] == "Best" and
        8 <= protein_percentage <= 43 and
        (carbs_percentage > 65 or fats_percentage > 30)
    ):
        end_result["End Result"] = "Moderate"

    # Apply Low Carbs Rule Overrule
    if (
        45 <= carbs_percentage <= 60  # Carbs in Best range
    ):
        if (
            8 <= protein_percentage <= 43 and  # Protein in Best range
            fats_percentage <= 35  # Fats slightly higher
        ):
            end_result["End Result"] = "Best"
        elif (
            (3 <= protein_percentage <= 8 or 44 <= protein_percentage <= 58) and  # Protein in Moderate range
            fats_percentage <= 10  # Fats slightly lower
        ):
            # print(f"{dish_name} downgraded to 'Moderate' from Low Carbs Rule Overrule.")
            end_result["End Result"] = "Moderate"

    # Apply Low Fat Rule Overrule
    if (
        15 <= fats_percentage <= 30  # Fats in Best range
    ):
        if (
            8 <= protein_percentage <= 43 and  # Protein is optimal
            carbs_percentage <= 65  # Carbs slightly higher
        ):
            # print(f"{dish_name} remains 'Best' from Low Fat Rule Overrule.")
            end_result["End Result"] = "Best"
        elif (
            (3 <= protein_percentage <= 8 or 44 <= protein_percentage <= 58) and  # Protein is moderate
            45 <= carbs_percentage <= 60  # Carbs are balanced
        ):
            # print(f"{dish_name} downgraded to 'Moderate' from Low Fat Rule Overrule.")
            end_result["End Result"] = "Moderate"

    # Apply Sugar Content Rule
    if sugar_percentage > 30:
        # print(f"{dish_name} downgraded to 'Avoid' from Sugar Content Rule.")
        end_result["End Result"] = "Avoid"
    elif sugar_percentage > 20:
        if end_result["End Result"] == "Moderate":
            # print(f"{dish_name} downgraded to 'Avoid' from Sugar Content Rule.")
            end_result["End Result"] = "Avoid"
    elif sugar_percentage > 10:
        if end_result["End Result"] == "Best":
            # print(f"{dish_name} downgraded to 'Moderate' from Sugar Content Rule.")
            end_result["End Result"] = "Moderate"

    # Apply Sodium Content Rule
    if sodium_per_100g > 1200:
        # print(f"{dish_name} downgraded to 'Avoid' from Sodium Content Rule.")
        end_result["End Result"] = "Avoid"
    elif sodium_per_100g > 800:
        if end_result["End Result"] == "Moderate":
            # print(f"{dish_name} downgraded to 'Avoid' from Sodium Content Rule.")
            end_result["End Result"] = "Avoid"
    elif sodium_per_100g > 400:
        if end_result["End Result"] == "Best":
            # print(f"{dish_name} downgraded to 'Moderate' from Sodium Content Rule.")
            end_result["End Result"] = "Moderate"

    # Apply Cholesterol Rule
    if cholesterol_per_100g > 200:
        # print(f"{dish_name} downgraded to 'Avoid' from Cholesterol Rule.")
        end_result["End Result"] = "Avoid"
    elif cholesterol_per_100g > 150:
        if end_result["End Result"] == "Moderate":
            # print(f"{dish_name} downgraded to 'Avoid' from Cholesterol Rule.")
            end_result["End Result"] = "Avoid"
    elif cholesterol_per_100g > 75:
        if end_result["End Result"] == "Best":
            # print(f"{dish_name} downgraded to 'Moderate' from Cholesterol Rule.")
            end_result["End Result"] = "Moderate"

    # Apply Maida rule
    if maida_percentage > 15:
        # print(f"{dish_name} downgraded to 'Avoid' from Maida Rule.")
        end_result["End Result"] = "Avoid"
    elif maida_percentage > 10:
        if end_result["End Result"] == "Moderate":
            # print(f"{dish_name} downgraded to 'Avoid' from Maida Rule.")
            end_result["End Result"] = "Avoid"
    elif maida_percentage > 5:
        if end_result["End Result"] == "Best":
            # print(f"{dish_name} downgraded to 'Moderate' from Maida Rule.")
            end_result["End Result"] = "Moderate"

    # Return the original End Result if no conditions apply
    logging.debug(f"end result is : {end_result}")
    return end_result

def assign_tags(user_input, menu):
    logging.debug(f"let's assign_tags : user_input = {user_input}, menu = {menu}")

    user_preferences = calculate_nutrient_percentages(user_input)

    # Define match criteria dynamically
    match_criteria = {
        "Carbs": {
            "Best": [user_preferences["Carbohydrates (%)"] - 10, user_preferences["Carbohydrates (%)"] + 5],
            "M-Lower": [[user_preferences["Carbohydrates (%)"] - 15, user_preferences["Carbohydrates (%)"] - 10.01]],
            "M-Higher": [[user_preferences["Carbohydrates (%)"] + 5.01, user_preferences["Carbohydrates (%)"] + 11]],
            "A-Lower": [[0, user_preferences["Carbohydrates (%)"] - 15.01]],
            "A-Higher": [[user_preferences["Carbohydrates (%)"] + 11.01, 99.99]]
        },
        "Protein": {
            "Best": [user_preferences["Protein (%)"] - 5, user_preferences["Protein (%)"] + 30],
            "M-Lower": [[user_preferences["Protein (%)"] - 10, user_preferences["Protein (%)"] - 5.01]],
            "M-Higher": [[user_preferences["Protein (%)"] + 30.01, user_preferences["Protein (%)"] + 46]],
            "Avoid": [[0, user_preferences["Protein (%)"] - 10.01]],
            "A-Higher": [[user_preferences["Protein (%)"] + 46.01, 99.99]]
        },
        "Fats": {
            "Best": [user_preferences["Fats (%)"] - 10, user_preferences["Fats (%)"] + 5],
            "M-Lower": [[user_preferences["Fats (%)"] - 15, user_preferences["Fats (%)"] - 10.01]],
            "M-Higher": [[user_preferences["Fats (%)"] + 5.01, user_preferences["Fats (%)"] + 11]],
            "A-Lower": [[0, user_preferences["Fats (%)"] - 15.01]],
            "A-Higher": [[user_preferences["Fats (%)"] + 11.01, 99.99]]
        }
    }


    tagged_dishes = []

    for dish in menu:
        try:
            # dish_name = dish["dish_name"]
            dish_name = dish.get("dish_name", "Default Name")
            distributed_percentage = dish.get("distributed_percentage", {})
            protein_percentage = float(distributed_percentage.get("proteins", "0").strip('%'))
            carbs_percentage = float(distributed_percentage.get("carbs", "0").strip('%'))
            fats_percentage = float(distributed_percentage.get("fats", "0").strip('%'))

            # Extract sugar data
            serving_size =float(dish["dish_variants"]["normal"]["full"]["serving"]["size"])
            carbs = dish["dish_variants"]["normal"]["full"]["calculate_nutrients"]["macro_nutrients"]
            sugar_data = dish["dish_variants"]["normal"]["full"]["calculate_nutrients"]["sugar"]
            total_carbs = next((item["value"] for item in carbs if item["name"] == "carbs"), 0)
            total_free_sugars = next((item["value"] for item in sugar_data if item["name"] == "total_free_sugars"), 0)
            # Extract sodium content
            minerals = dish["dish_variants"]["normal"]["full"]["calculate_nutrients"]["minerals"]
            sodium_content = next((item["value"] for item in minerals if item["name"] == "sodium"), 0)

            # Extract cholesterol content and serving size
            cholesterol_data = dish["dish_variants"]["normal"]["full"]["calculate_nutrients"]["cholesterol"]
            cholesterol_mg = next((item["value"] for item in cholesterol_data if item["name"] == "cholesterol"), 0)

            ingredients = dish["dish_variants"]["normal"]["full"]["ingredients"]
            maida_percentage = calculate_maida_percentage(ingredients, serving_size)

            # Calculate cholesterol per 100g
            cholesterol_per_100g = float((cholesterol_mg / serving_size) * 100) if serving_size > 0 else 0
            sodium_per_100g = float((sodium_content / serving_size) * 100 )if serving_size > 0 else 0
            sugar_percentage = float((total_free_sugars / total_carbs) * 100) if total_carbs > 0 else 0

            # Determine tags for each macronutrient
            protein_tag = find_range(protein_percentage, match_criteria["Protein"])
            carbs_tag = find_range(carbs_percentage, match_criteria["Carbs"])
            fats_tag = find_range(fats_percentage, match_criteria["Fats"])

            # Get the initial End Result
            initial_category = find_combination(protein_tag, carbs_tag, fats_tag)
            
            # Apply conditions to refine the category
            refined_category = apply_conditions(dish_name,initial_category, protein_percentage, carbs_percentage, fats_percentage, sugar_percentage, sodium_per_100g,cholesterol_per_100g,maida_percentage)
            # print(f"tagged_dishes: {tagged_dishes}")
            # print(f"dishhhhhh: {dish}")

            # Append the results for this dish #add all dishes with default one
            tagged_dishes.append({
                "dish_name": dish["dish_name"],
                "category": refined_category,
                "initial_category":initial_category,
                "protein": protein_tag,
                "carbs": carbs_tag,
                "fats": fats_tag,
                "protein_percentage": protein_percentage,
                "carbs_percentage": carbs_percentage,
                "fats_percentage": fats_percentage,
                "sugar_percentage" : sugar_percentage,
                "sugar carbs":total_carbs,
                "total_free_sugars":total_free_sugars
            })
        except KeyError as e:
            # print(f"Missing key in dish data: {e}")
            continue  # Skip this dish and proceed to the next
        
        except ValueError as e:
            # print(f"Value error: {e}. Skipping dish: {dish.get('dish_name', 'Unknown')}")
            continue  # Skip this dish and proceed to the next
        
        except Exception as e:
            # print(f"Unexpected error processing dish {dish.get('dish_name', 'Unknown')}: {e}")
            continue  # Skip this dish and proceed to the next
        
    return tagged_dishes



def combine_tags_into_dishes(restro_id, user_input):
    logging.info(f"Fetching and processing data for restro_id: {restro_id}")

    try:
        # Fetch restaurant menu data
        menu_data = menu_collection.find_one({"_id": restro_id})
        if not menu_data:
            logging.warning(f"No menu data found for restro_id: {restro_id}")
            return {"error": "Restaurant data not found"}

        menu = menu_data.get("menu", [])

        # Assign tags to the dishes
        tagged_dishes = assign_tags(user_input, menu)

        folder_name = "dishes_output"
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        output_file = os.path.join(folder_name, "tagged_dishes.json")
        with open(output_file, "w") as json_file:
            json.dump(tagged_dishes, json_file, indent=4)

        best_dishes = [
            dish["dish_name"]
            for dish in tagged_dishes
            if dish.get("category", {}).get("End Result") == "Best"
        ]

        good_dishes = [
            dish["dish_name"]
            for dish in tagged_dishes
            if dish.get("category", {}).get("End Result") == "Moderate"
        ]

    
        # Append tags to the corresponding dish in the menu
        for dish, tagged_dish in zip(menu, tagged_dishes):
            # Update the dish object with tagged data
            dish.update({
                "category": tagged_dish["category"],
                "initial_category": tagged_dish["initial_category"],
                "protein_tag": tagged_dish["protein"],
                "carbs_tag": tagged_dish["carbs"],
                "fats_tag": tagged_dish["fats"],
                "protein_percentage": tagged_dish["protein_percentage"],
                "carbs_percentage": tagged_dish["carbs_percentage"],
                "fats_percentage": tagged_dish["fats_percentage"],
                "sugar_percentage": tagged_dish["sugar_percentage"],
                "sugar_carbs": tagged_dish["sugar carbs"],
                "total_free_sugars": tagged_dish["total_free_sugars"]
            })

        menu_data["menu"] = menu  


        return best_dishes, good_dishes

    except Exception as e:
        logging.error(f"Error combining data into dishes: {e}")
        return {"error": str(e)}
    
def calculate_nutrient_percentages(user_input):
        print("user model is running...")
        tdee = user_input["Fixed Calories"]
        age = user_input["Age"]
        gender = user_input["Gender"]
        goal = user_input["Goal"]
        weight = user_input["Weight (kg)"]  

        print(age, gender, goal,weight)

        logging.debug(f"let's calculating nutrient percentage : age = {age}, gender = {gender}, goal = {goal}, weight = {weight}")

        protein_min = protein_max = carbs_min = carbs_max = fats_min = fats_max = fiber = 0

        # Clamp the age within the supported range
        if age < 18:
            age = 18
        elif age > 60:
            age = 60

        # Initialize boundaries and nutrient percentages for each group
        if goal == "Muscle Gain":
            if gender == "Male":
                if 18 <= age <= 40:
                    protein_min, protein_max = 20, 25
                    carbs_min, carbs_max = 50, 55
                    fats_min, fats_max = 20, 25
                    fiber_min,fiber_max = 10,13
                    prot_g_low, prot_g_high = 1.6, 2.2
                elif 40 < age <= 60:
                    protein_min, protein_max = 15, 20
                    carbs_min, carbs_max = 50, 55
                    fats_min, fats_max = 25, 30
                    prot_g_low, prot_g_high = 1.2, 1.5
                    fiber_min,fiber_max = 6,9
            elif gender == "Female":
                if 18 <= age <= 40:
                    protein_min, protein_max = 20, 22
                    carbs_min, carbs_max = 50, 55
                    fats_min, fats_max = 20, 25
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 1.4, 1.8
                elif 40 < age <= 60:
                    protein_min, protein_max = 15, 20
                    carbs_min, carbs_max = 50, 55
                    fats_min, fats_max = 25, 30
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 1.2, 1.5

        elif goal == "Weight Loss":
            if gender == "Male":
                if 18 <= age <= 40:
                    protein_min, protein_max = 20, 25
                    carbs_min, carbs_max = 40, 45
                    fats_min, fats_max = 30, 35
                    fiber_min,fiber_max = 10,13
                    prot_g_low, prot_g_high = 1.8, 2.2
                elif 40 < age <= 60:
                    protein_min, protein_max = 18, 20
                    carbs_min, carbs_max = 45, 50
                    fats_min, fats_max = 30, 35
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 1.4, 1.8
            elif gender == "Female":
                if 18 <= age <= 40:
                    protein_min, protein_max = 18, 22
                    carbs_min, carbs_max = 40, 45
                    fats_min, fats_max = 30, 35
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 1.6, 2.0
                elif 40 < age <= 60:
                    protein_min, protein_max = 18, 20
                    carbs_min, carbs_max = 45, 50
                    fats_min, fats_max = 30, 35
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 1.4, 1.8

        elif goal == "Healthy Eating":
            if gender == "Male":
                if 18 <= age <= 40:
                    protein_min, protein_max = 10, 15
                    carbs_min, carbs_max = 55, 60
                    fats_min, fats_max = 20, 25
                    fiber_min,fiber_max = 10,13
                    prot_g_low, prot_g_high = 0.8, 1.2
                elif 40 < age <= 60:
                    protein_min, protein_max = 10, 12
                    carbs_min, carbs_max = 50, 55
                    fats_min, fats_max = 25, 30
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 0.8, 1.0
            elif gender == "Female":
                if 18 <= age <= 40:
                    protein_min, protein_max = 10, 12
                    carbs_min, carbs_max = 55, 60
                    fats_min, fats_max = 20, 25
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 0.8, 1.0
                elif 40 < age <= 60:
                    protein_min, protein_max = 10, 12
                    carbs_min, carbs_max = 50, 55
                    fats_min, fats_max = 25, 30
                    fiber_min,fiber_max = 6,9
                    prot_g_low, prot_g_high = 0.8, 1.0

        # Calculate nutrient percentages using linear interpolation
        age_range = (18, 40) if age <= 40 else (40, 60)
        protein_factor = (protein_max - protein_min) / (age_range[1] - age_range[0])
        protein_g_factor = (prot_g_high - prot_g_low) / (age_range[1] - age_range[0])
        carbs_factor = (carbs_max - carbs_min) / (age_range[1] - age_range[0])
        fats_factor = (fats_max - fats_min) / (age_range[1] - age_range[0])
        fiber_factor = (fiber_max - fiber_min) / (age_range[1] - age_range[0])

        protein_percentage = protein_min + ((age - age_range[0]) * protein_factor)
        protein_g = prot_g_low + ((age - age_range[0]) * protein_g_factor)
        carbs_percentage = carbs_max - ((age - age_range[0]) * carbs_factor)  # Invert for decrease
        fats_percentage = fats_min + ((age - age_range[0]) * fats_factor)
        fiber_grams = max(fiber_min, min(fiber_max, fiber_min + ((age - age_range[0]) * fiber_factor)))
        fiber_kcal = fiber_grams*2
        tdee1 = tdee - fiber_kcal

        # Calculate actual nutrient values
        proteink = (protein_percentage * tdee1) / 100
        protein_g1 = (weight * protein_g)
        protein = max(proteink, protein_g1)  # Ensure we are getting the correct protein value

        fats = (tdee1 * fats_percentage) / 100
        carbs = tdee - fiber_kcal - fats - protein
        # Now, you can return the correct fiber in grams and as a percentage
        p = (protein / 4)  # Protein in grams (1g protein = 4 calories)
        f = (fats / 9)  # Fats in grams (1g fat = 9 calories)
        c = (carbs / 4)  # Carbs in grams (1g carbs = 4 calories)

        return {
            "Protein (%)": round(((protein * 100) / tdee), 2),
            "Carbohydrates (%)": round(((carbs * 100) / tdee), 2),
            "Fats (%)": round(((fats * 100) / tdee), 2),
            "Fiber (g/day)": round(fiber_grams, 2),  # Return fiber in grams
            "p": round(p, 2),  # Protein in grams
            "c": round(c, 2),  # Carbs in grams
            "fa": round(f, 2),  # Fats in grams
            "fiber": round(fiber_grams, 2),  # Fiber in grams (to avoid confusion with percentage)
            "tdee": round(tdee, 2)  # Total Daily Energy Expenditure (TDEE)
        }

def filter_dishes(all_dishes, dish_names, match_type):
    filtered_dishes = []
    seen = set()  # To avoid duplicates
    for dish in all_dishes:
        if dish.get("dish_name") in dish_names and dish.get("dish_name") not in seen:
            dish["match"] = match_type
            filtered_dishes.append(dish)
            seen.add(dish.get("dish_name"))  # Track added dishes
    return filtered_dishes

def default_goal_dishes(restro_id, user_id):

    User = fetch_user_data(user_id)
    user_input = user_data_process(User)

    tdee=  user_input["Fixed Calories"]
    age = user_input["Age"]
    gender = user_input["Gender"]
    goal = user_input["Goal"]
    weight = user_input["Weight (kg)"]

    all_dishes = fetch_dishes_by_restro_id(restro_id)
    best_dishes, good_dishes = combine_tags_into_dishes(restro_id, user_input)
    # print(f"best_dishes from combine tags into dishes: {best_dishes}")

    if not best_dishes:
        best_dishes = "no result"

    if not good_dishes:
        good_dishes = "no result"

    all_dishes_flat = []
    for restaurant in all_dishes:
        all_dishes_flat.extend(restaurant.get("menu", []))

    best_all_dishes_flat = []
    # save_json_to_file(best_dishes, "dishes_output", "dish.json")

    for dish_name in best_dishes:  
        restaurant_data = menu_collection.find_one({"menu.dish_name": dish_name})  
        if restaurant_data:  
            best_all_dishes_flat.extend(restaurant_data.get("menu", []))
        else:
            print(f"WARNING: No menu found for {dish_name}")  


# Good Dishes

    good_all_dishes_flat = []

    # If best_dishes contains only names, you need to fetch menu data differently
    for dish_name in good_dishes:
        # print("DEBUG: Processing dish =", dish_name)  
        restaurant_data = menu_collection.find_one({"menu.dish_name": dish_name})  

        if restaurant_data:  
            good_all_dishes_flat.extend(restaurant_data.get("menu", []))
        else:
            print(f"WARNING: No menu found for {dish_name}")  

    # categorized_dishes = [
#     {
#         "dishes": filter_dishes(all_dishes=best_all_dishes_flat, dish_names=best_dishes, match_type="Best Match")
#     },
#     {
#         "dishes": filter_dishes(all_dishes=good_all_dishes_flat, dish_names=good_dishes, match_type="Good Match")
#     }
# ]
    categorized_dishes = [
    {
        "dishes": filter_dishes(all_dishes=best_all_dishes_flat, dish_names=best_dishes, match_type="Best Match")
    },
    {
        "dishes": filter_dishes(all_dishes=good_all_dishes_flat, dish_names=good_dishes, match_type="Good Match")
    }
]
    return categorized_dishes

