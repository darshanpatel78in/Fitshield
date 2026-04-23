# Define the mapping globally
import json

display_name_mapping = {
    # "PROTCNT": "Protein",
    "Protein":"PROTCNT",
    "ASH": "Total minerals",
    "FATCE": "Total fats",
    "FIBTG": "Total dietary fiber",
    "FIBSOL": "Soluble fiber",
    "FIOBINS": "Insoluble fiber",
    "CHOAVLDF": "Carbohydrate",
    "ENERC": "Energy",
    "THIA": "Vitamin B1",
    "RIBF": "Vitamin B2",
    "NIA": "Vitamin B3",
    "PANTAC": "Vitamin B5",
    "VITB6C": "Vitamin B6",
    "VITC": "Vitamin C",
    "BIOT": "Vitamin B7",
    "FOLSUM": "Vitamin B9",
    "RETOL": "Vitamin A",
    "ERGCAL": "Vitamin D2",
    "CHOCAL": "Vitamin D3",
    "VITK1": "Vitamin K1",
    "VITK2": "Vitamin K2",
    "CARTOID": "Provitamin A",
    "VITE": "Vitamin E",
    "AL": "Aluminum",
    "CD": "Cadmium",
    "CA": "Calcium",
    "CR": "Chromium",
    "CO": "Cobalt",
    "CU": "Copper",
    "FE": "Iron",
    "PB": "Lead",
    "LI": "Lithium",
    "MG": "Magnesium",
    "MN": "Manganese",
    "MO": "Molybdenum",
    "NI": "Nickel",
    "P": "Phosphorus",
    "K": "Potassium",
    "NA": "Sodium",
    "ZN": "Zinc",
    "AS": "Arsenic",
    "HG": "Mercury",
    "SE": "Selenium",
    "TCHO": "Total available Carbohydrate",
    "STARCH": "Starch : Complex carbs",
    "FRUS": "Fructose",
    "GLUS": "Glucose",
    "SUCS": "Sucrose",
    "MALS": "Maltose",
    "FASAT": "Total Saturated Fatty acids",
    "FAMS": "Total Monosaturated fatty acids",
    "FAPU": "Omega-3s, Omega 6s",
    "energy": "Energy",
    "carbs": "Carbs",
    "proteins": "Proteins",
    "fats": "Fats",
    "fibers": "Fibers",
    "thiamin": "Vitamin B1",
    "riboflavin": "Vitamin B2",
    "niacin": "Vitamin B3",
    "vitamin_b5": "Vitamin B5",
    "vitamin_b6": "Vitamin B6",
    "vitamin_c": "Vitamin C",
    "biotin": "Biotin",
    "folate": "Folate",
    "vitamin_a": "Vitamin A",
    "vitamin_d2": "Vitamin D2",
    "vitamin_d3": "Vitamin D3",
    "vitamin_k1": "Vitamin K1",
    "vitamin_k2": "Vitamin K2",
    "carotenoids": "Carotenoids",
    "vitamin_e": "Vitamin E",
    "aluminium": "Aluminium",
    "cadmium": "Cadmium",
    "calcium": "Calcium",
    "chromium": "Chromium",
    "cobalt": "Cobalt",
    "copper": "Copper",
    "iron": "Iron",
    "lead": "Lead",
    "lithium": "Lithium",
    "magnesium": "Magnesium",
    "manganese": "Manganese",
    "molybdenum": "Molybdenum",
    "nickel": "Nickel",
    "phosphorus": "Phosphorus",
    "potassium": "Potassium",
    "sodium": "Sodium",
    "zinc": "Zinc",
    "arsenic": "Arsenic",
    "mercury": "Mercury",
    "selenium": "Selenium",
    "total_saturated_fats": "Total Saturated Fats",
    "total_monounsaturated_fats": "Total Monounsaturated Fats",
    "total_polyunsaturated_fats": "Total Polyunsaturated Fats",
    "cholesterol": "Cholesterol",
    "total_carbohydrates": "Total Carbohydrates",
    "starch": "Starch",
    "fructose": "Fructose",
    "glucose": "Glucose",
    "sucrose": "Sucrose",
    "maltose": "Maltose",
    "total_free_sugars": "Total Free Sugars",
    "total_minerals": "Total Minerals",
    "soluble_fiber": "Soluble Fiber",
    "insoluble_fiber": "Insoluble Fiber",
    "macro_nutrients": "Macro Nutrients",
    "water_soluble_vitamin": "Water Soluble Vitamin",
    "fat_soluble_vitamin": "Fat Soluble Vitamin",
    "minerals": "Minerals",
    "fatty_acid_profile": "Fatty Acid Profile",
    "cholesterol": "Cholesterol",
    "sugar": "Sugar",
    "other": "Other"
}


def get_display_name(key):
    return display_name_mapping.get(key, key)



def replace_macronutrients_with_display_names(data):

    def format_category_name(key):
        return " ".join(word.capitalize() for word in key.split("_"))

    if isinstance(data, dict):
        for key in list(data.keys()):
            if key == "dish_variants" and isinstance(data[key], dict):
                variants = data[key].get("normal", {}).get("full", {})

                # Process `calculate_nutrients`
                if "calculate_nutrients" in variants and isinstance(variants["calculate_nutrients"], dict):
                    calculate_nutrients = variants["calculate_nutrients"]
                    for nutrient_type, nutrients in calculate_nutrients.items():
                        if isinstance(nutrients, list):
                            for nutrient in nutrients:
                                if "name" in nutrient and nutrient["name"] in display_name_mapping:
                                    # Replace the short name with the full name
                                    nutrient["name"] = get_display_name(nutrient["name"])
                    
                    # Replace the `calculate_nutrients` key with its formatted name
                    variants[format_category_name("calculate_nutrients")] = variants.pop("calculate_nutrients")

                # Process `nutrients`
                if "nutrients" in variants and isinstance(variants["nutrients"], list):
                    for nutrient in variants["nutrients"]:
                        if "name" in nutrient and nutrient["name"] in display_name_mapping:
                            # Replace the short name with the full name
                            nutrient["name"] = get_display_name(nutrient["name"])
                    
                    # Replace the `nutrients` key with its formatted name
                    variants[format_category_name("Nutrients")] = variants.pop("nutrients")

            # Process keys inside `calculate_nutrients` at a deeper level
            if key == "calculate_nutrients" and isinstance(data[key], dict):
                for nutrient_type, nutrients in data[key].items():
                    if isinstance(nutrients, list):
                        for nutrient in nutrients:
                            if "name" in nutrient and nutrient["name"] in display_name_mapping:
                                # Replace the short name with the full name
                                nutrient["name"] = get_display_name(nutrient["name"])

            # Recursively process nested dictionaries or lists
            if isinstance(data[key], (dict, list)):
                data[key] = replace_macronutrients_with_display_names(data[key])

            # Format top-level category keys (like `macro_nutrients`)
            if key in display_name_mapping:
                data[format_category_name(key)] = data.pop(key)
        return data

    elif isinstance(data, list):
        return [replace_macronutrients_with_display_names(item) for item in data]

    return data  
