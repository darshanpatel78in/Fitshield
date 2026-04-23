

import json
import os

from django.http import JsonResponse

from fitshield.settings import  MIN_DISH_LEVEL
from fitshield_webapp.view.restro.save_json import save_json_to_file
from .data import possibilities
from config.connection import db

menu_collection = db["RestaurantMenuData"]
user_data_collection = db["UserData"]

# def fetch_dishes_by_restro_id(restro_id):
#     dishes = list(menu_collection.find({"_id": restro_id}))
#     return dishes


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

def calculate_nutrient_percentages(tdee, age, gender, goal, weight):
    print(tdee,age,gender,weight)
    protein_min = protein_max = carbs_min = carbs_max = fats_min = fats_max = fiber = 0

    # 1) Age clamp
    if age < 18:
        age = 18
    elif age > 60:
        age = 60

        # 2) Initialize boundaries based on goal + gender
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
    c = (carbs / 4)  # Carbs in grams (1g carbs = 4 calories

    return {
        "p": round(p, 2),  # Protein in grams
        "c": round(c, 2),  # Carbs in grams
        "fa": round(f, 2),  # Fats in grams
        "fiber": round(fiber_grams, 2),  # Fiber in grams (to avoid confusion with percentage)
        "tdee": round(tdee, 2)  # Total Daily Energy Expenditure (TDEE)
    }

def find_combination(protein_category, carbs_category, fats_category):
    for possibility in possibilities:
        if (possibility["Protein"] == protein_category and
            possibility["Carbs"]   == carbs_category   and
            possibility["Fats"]    == fats_category):
            return {"End Result": possibility["End Result"]}
    return {"End Result": "Avoid"}

def find_range(value, ranges):
    for tag_name, range_values in ranges.items():
        if isinstance(range_values[0], list):
            for sub_range in range_values:
                if sub_range[0] <= value <= sub_range[1]:
                    return tag_name
        else:
            if range_values[0] <= value <= range_values[1]:
                return tag_name
    return "Avoid"

def calculate_maida_percentage(ingredients, serving_size):
    maida_qty  = 0
    total_qty  = 0
    for ing in ingredients:
        q = float(ing.get("quantity",0))
        total_qty += q
        if ("maida" in ing["name"].lower() or "refined flour" in ing["name"].lower()):
            maida_qty += q
    if serving_size>0:
        return (maida_qty / serving_size)*100
    elif total_qty>0:
        return (maida_qty / total_qty)*100
    return 0

def apply_conditions(
    dish_name, end_result,
    protein_percentage, carbs_percentage, fats_percentage,
    sugar_percentage, sodium_per_100g, cholesterol_per_100g, maida_percentage
):
    if (end_result["End Result"] == "Best"
        and 8 <= protein_percentage <= 43
        and (carbs_percentage > 65 or fats_percentage >30)):
        end_result["End Result"] = "Moderate"

    return end_result

# def classify_dishes_with_custom_percentage(
#     menu,
#     # SCENARIO B: direct macros
#     carbs_g=None,
#     protein_g=None,
#     fats_g=None,
#     fiber_g=None,
#     # SCENARIO A: pass daily_kcal + age/gender/goal/weight
#     daily_kcal=None,
#     age=None,
#     gender=None,
#     goal=None,
#     weight=None
# ):

tagged_dishes = []

def classify_dishes_with_custom_percentage(carbs_g, protein_g,fats_g, fiber_g, menu):

    # Check macros
    has_4_macros = (carbs_g is not None and protein_g is not None and fats_g is not None)

    if has_4_macros:
        # SCENARIO B
        # 1) Compute total
        # print(fiber_g)
        fiber_val = fiber_g if fiber_g else 0
        # fiber_val = 0

        total_cals = (carbs_g*4) + (protein_g*4) + (fats_g*9) + (fiber_val*2)


        if total_cals<=0:
            return {
                "macro_info": {},
                "dishes": []
            }

        user_carbs_pct   = (carbs_g*4    / total_cals)*100
        user_protein_pct = (protein_g*4  / total_cals)*100
        user_fats_pct    = (fats_g*9     / total_cals)*100

        # We'll store these in "macro_info"
        macro_info = {
            "total_kcal": round(total_cals,1),
            "protein_g":  round(protein_g,1),
            "carbs_g":    round(carbs_g,1),
            "fats_g":     round(fats_g,1),
            "fiber_g":    round(fiber_val,1)
        }

    # else:
    #     # SCENARIO A
    #     print("\nSCENARIO A: Using calculate_nutrient_percentages + daily_kcal")
    #     if not daily_kcal or not age or not gender or not goal or not weight:
    #         print("Error: must provide daily_kcal, age, gender, goal, weight.")
    #         return {
    #             "macro_info": {},
    #             "dishes": []
    #         }

    #     # 1) run your snippet-based logic => get final percentages
    #     snippet_result = calculate_nutrient_percentages(daily_kcal, age, gender, goal, weight)
    #     # snippet_result => e.g. {"Protein (%)": 22.5, "Carbohydrates (%)":48.3, "Fats (%)":29.2, "Fiber (g/day)": 50}

    #     user_protein_pct = snippet_result["Protein (%)"]
    #     user_carbs_pct   = snippet_result["Carbohydrates (%)"]
    #     user_fats_pct    = snippet_result["Fats (%)"]
    #     user_fiber_day   = snippet_result["Fiber (g/day)"]  # total fiber per day

    #     # 2) Convert those percentages => grams from daily_kcal
    #     #    - protein_g = (protein_%/100 * daily_kcal)/4
    #     #    - carbs_g   = (carbs_%/100   * daily_kcal)/4
    #     #    - fats_g    = (fats_%/100    * daily_kcal)/9
    #     #    - fiber_g   = user_fiber_day (the snippet value)
    #     protein_kcal = (user_protein_pct/100)* daily_kcal
    #     carbs_kcal   = (user_carbs_pct/100)  * daily_kcal
    #     fats_kcal    = (user_fats_pct/100)   * daily_kcal

    #     prot_g   = protein_kcal/4
    #     carb_g   = carbs_kcal/4
    #     fat_g    = fats_kcal/9
    #     fiberVal = user_fiber_day  # from snippet

    #     macro_info = {
    #         "total_kcal": round(daily_kcal,1),
    #         "protein_g":  round(prot_g,1),
    #         "carbs_g":    round(carb_g,1),
    #         "fats_g":     round(fat_g,1),
    #         "fiber_g":    round(fiberVal,1)
    #     }

    # print("Macro distribution =>", macro_info)

    # Build match criteria from user_carbs_pct, user_protein_pct, user_fats_pct
    match_criteria = {
        "Carbs": {
            "Best":      [user_carbs_pct - 10, user_carbs_pct + 5],
            "M-Lower":   [[user_carbs_pct - 15, user_carbs_pct - 10.01]],
            "M-Higher":  [[user_carbs_pct + 5.01, user_carbs_pct + 11]],
            "A-Lower":   [[0, user_carbs_pct - 15.01]],
            "A-Higher":  [[user_carbs_pct + 11.01, 99.99]]
        },
        "Protein": {
            "Best":      [user_protein_pct - 5, user_protein_pct + 30],
            "M-Lower":   [[user_protein_pct - 10, user_protein_pct - 5.01]],
            "M-Higher":  [[user_protein_pct + 30.01, user_protein_pct + 46]],
            "Avoid":     [[0, user_protein_pct - 10.01]],
            "A-Higher":  [[user_protein_pct + 46.01, 99.99]]
        },
        "Fats": {
            "Best":      [user_fats_pct - 10, user_fats_pct + 5],
            "M-Lower":   [[user_fats_pct - 15, user_fats_pct - 10.01]],
            "M-Higher":  [[user_fats_pct + 5.01, user_fats_pct + 11]],
            "A-Lower":   [[0, user_fats_pct - 15.01]],
            "A-Higher":  [[user_fats_pct + 11.01, 99.99]]
        }
    }
    # save_json_to_file(menu, "dishes_output", "menuuuuuu.json")

    # Classify each dish
    # tagged_dishes = []
    for dish in menu:

        dish_name   = dish["dish_name"]

        dist_perc   = dish.get("distributed_percentage",{})

        protein_pct = float(dist_perc.get("proteins","0").strip('%'))
        carbs_pct   = float(dist_perc.get("carbs","0").strip('%'))
        fats_pct    = float(dist_perc.get("fats","0").strip('%'))

        # parse for apply_conditions
        normal_variant = dish["dish_variants"]["normal"]["full"]
        serving_size   = float(normal_variant["serving"]["size"])
        macro_data     = normal_variant["calculate_nutrients"]["macro_nutrients"]
        sugar_data     = normal_variant["calculate_nutrients"]["sugar"]
        total_carbs_val  = next((m["value"] for m in macro_data if m["name"]=="carbs"),0)
        total_free_sugars= next((s["value"] for s in sugar_data if s["name"]=="total_free_sugars"),0)

        minerals       = normal_variant["calculate_nutrients"]["minerals"]
        sodium_content = next((m["value"] for m in minerals if m["name"]=="sodium"),0)

        chol_data      = normal_variant["calculate_nutrients"]["cholesterol"]
        chol_val       = next((c["value"] for c in chol_data if c["name"]=="cholesterol"),0)

        ingredients    = normal_variant["ingredients"]
        maida_pct      = calculate_maida_percentage(ingredients,serving_size)

        sugar_pct      = (total_free_sugars/total_carbs_val*100) if total_carbs_val>0 else 0
        sodium_per_100g= (sodium_content / serving_size)*100 if serving_size>0 else 0
        chol_per_100g  = (chol_val / serving_size)*100 if serving_size>0 else 0

        # Step 1: find tags
        protein_tag = find_range(protein_pct, match_criteria["Protein"])
        carbs_tag   = find_range(carbs_pct,   match_criteria["Carbs"])
        fats_tag    = find_range(fats_pct,    match_criteria["Fats"])

        # Step 2: initial category
        initial_cat = find_combination(protein_tag, carbs_tag, fats_tag)

        # Step 3: overrule
        final_cat = apply_conditions(
            dish_name,
            initial_cat,
            protein_pct,
            carbs_pct,
            fats_pct,
            sugar_pct,
            sodium_per_100g,
            chol_per_100g,
            maida_pct
        )
        tagged_dishes.append({
            "dish_name": dish_name,
            "initial_category": initial_cat,
            "final_category": final_cat,
            "protein_tag": protein_tag,
            "carbs_tag": carbs_tag,
            "fats_tag": fats_tag,
            "protein_percentage": protein_pct,
            "carbs_percentage": carbs_pct,
            "fats_percentage": fats_pct, 
            "sugar_percentage": sugar_pct,
            "maida_percentage": maida_pct,
            "sodium_per_100g": sodium_per_100g,
            "cholesterol_per_100g": chol_per_100g
        })

        # Return both macro info + dish results

    return  tagged_dishes

# print("Using KCAL get personalize dishes")
# scenarioA_output = classify_dishes_with_custom_percentage(daily_kcal=2000, age=25, gender="Female", goal="Muscle Gain", weight=68)
# print("\n--- Macro Info ---")
# print(scenarioA_output["macro_info"])
# print("\n--- Dish Classification ---")
# for d in scenarioA_output["dishes"]:
#     print(d)

def fetch_user_data(user_id):

    User = user_data_collection.find_one({"_id": user_id})

    if not User:
        return None
    return User


def fetch_menu_data(restro_id):
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

# go to user_id  and get all 4 values
def live_goal_dishes(restro_id, user_id):
    User = fetch_user_data(user_id)

    if not User or "goals" not in User or "live_goal" not in User["goals"]:
        return None
    
    nutrients = User["goals"]["live_goal"]["nutrients"]
    carbs_g = nutrients["carbs"].get("value", 0)
    protein_g = nutrients["protein"].get("value", 0)
    fats_g = nutrients["fats"].get("value", 0)
    fiber_g = nutrients["fiber"].get("value", 0)
    
    menu = fetch_menu_data(restro_id)

# print("Using cpff get personalize dishes")
    tagged_dishes = classify_dishes_with_custom_percentage(carbs_g, protein_g,fats_g, fiber_g, menu)

    best_dishes = [
        dish["dish_name"]
        for dish in tagged_dishes
        if "initial_category" in dish and dish["initial_category"].get("End Result") == "Best"
    ]
    good_dishes = [
        dish["dish_name"]
        for dish in tagged_dishes
        if "initial_category" in dish and dish["initial_category"].get("End Result") == "Moderate"
    ]
    # print(best_dishes)
    # print(good_dishes)
    # Append tags to the corresponding dish in the menu
    for dish, tagged_dish in zip(menu, tagged_dishes):
        # Update the dish object with tagged data
        dish.update({
            "initial_category": tagged_dish["initial_category"],
        })
    
       
    

    # Filter dishes based on names and append match key
    def filter_dishes(dish_names, match_type):
        filtered_dishes = []

        all_dishes = fetch_dishes_by_restro_id(restro_id)
        all_dishes_flat = []
        # for restaurant in all_dishes:
        #     all_dishes_flat.extend(restaurant.get("menu", []))

        for dish in all_dishes:
            if dish.get("dish_name") in dish_names:
                # Append the match key to the dish
                dish_copy = dish.copy()  # Avoid modifying original data
                dish_copy["match"] = match_type
                filtered_dishes.append(dish_copy)
        return filtered_dishes

   # Organize the dishes
    categorized_dishes = [
        {   
            "dishes": filter_dishes(best_dishes, "Best Match")
        },
        {
            "dishes": filter_dishes(good_dishes, "Good Match")
        }
    ]

    return categorized_dishes
