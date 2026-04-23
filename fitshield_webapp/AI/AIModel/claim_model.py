import re

rda_values = {
    "fibers": 40, # g/day
    "proteins": 54, #g
    "thiamin": 1.8, #mg
    "riboflavin": 2.5, #mg
    "niacin": 18, #mg
    "vitamin_b5": 5, #mg
    "vitamin_b6": 2.4, #mg
    "vitamin_c": 80, #mg
    "biotin": 25,  #ug
    "folate": 300, #ug
    "vitamin_a": 1000, #ug
    "vitamin_d": 15, #ug # e
    "vitamin_k": 55, #ug # e
    "vitamin_e": 9, #mg
    "calcium": 1000, #mg,
    "copper": 17, #mg
    "iron": 19, #mg
    "magnesium": 440, #mg
    "manganese": 4, #mg
    "phosphorus": 600, #mg  # e
    "potassium": 3500, #mg
    "zinc": 17, #mg,
    #"sodium": 2000 #mg
}

unit_conversion = {
    "g": 1,        # 1 gram = 1 gram
    "kg": 1000,    # 1 kilogram = 1000 grams
    "mg": 0.001,   # 1 milligram = 0.001 grams
    "µg": 0.000001, # 1 microgram = 0.000001 grams
}

replacement_map = {
    "thiamin": "Vitamin B1",
    "riboflavin": "Vitamin B2",
    "niacin": "Vitamin B3",
    "biotin": "Vitamin B7",
    "folate": "Vitamin B9",
    "carotenoids": "Provitamin A"
}

max_limits = {
    "niacin": 35, #mg
    "vitamin_b6": 100, #mg
    "vitamin_c": 2000, #mg
    "folate": 1000, #μg
    "vitamin_a": 3000, #μg
    "vitamin_d": 100, #μg
    "vitamin_e": 1000, #mg
    "calcium": 2500, #mg
    "iron": 45, #mg
    "phosphorus": 4000, #mg
    "zinc": 40, #mg
    "copper": 10, #mg
    "manganese": 11 #mg
}

gluten_ingredients = ["wheat","flour","barley","rye","malt","farina","semolina","spelt","triticale","bulgur","couscous"]
lactose_ingredients = ["milk","cream","butter","yogurt","cheese","whey","curd","milk powder","milk solids","evaporated milk","condensed milk","paneer"]

fassi_guidelines = "https://fssai.gov.in/upload/uploadfiles/files/Compendium_Advertising_Claims_Regulations_04_03_2021.pdf"

def get_the_nutrients_tags(data):

    tags = []
    details_of_claims = []
    remain_data = []
    serving_size = float(data["dish_variants"]["normal"]["full"]["serving"]["size"])  # Serving size in grams or milliliters
    unit = data["dish_variants"]["normal"]["full"]["serving"]["unit"].lower()  # Get the unit (g or ml)

#____________________________ saturated_fats _______________________________________________________________________________________________________________________________

    saturated_fats_low = 1500 if unit == "g" else 750 #in mg
    saturated_fats_low_guideline = "If it has 1500 mg or less per 100 grams." if unit == "g" else "If it has 750 mg or less per 100 ml."
    saturated_fats_free = 100 #in mg
    saturated_fats_free_guideline = "If it has no more than 100 mg per 100 grams." if unit == "g" else "If it has no more than 100 mg per 100 ml."

    saturated_fats_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_saturated_fats")
    total_saturated_fats =  next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_saturated_fats")

    # Calculate saturated fats per 100g
    saturated_fats_per_100g = (total_saturated_fats / serving_size) * 100

    if saturated_fats_per_100g < saturated_fats_free:
        tags.append("Saturated Fats Free")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Saturated Fats Free",
                    "Name of Nutrients": "Saturated Fats",
                    "Value": total_saturated_fats,
                    "Unit": saturated_fats_unit,
                    "Convertion for claims" : round(saturated_fats_per_100g,2),
                    "Guideline": saturated_fats_free_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
        
    elif saturated_fats_per_100g < saturated_fats_low:
        tags.append("Low in Saturated Fats")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Low in Saturated Fats",
                    "Name of Nutrients": "Saturated Fats",
                    "Value": total_saturated_fats,
                    "Unit": saturated_fats_unit,
                    "Convertion for claims" : round(saturated_fats_per_100g,2),
                    "Guideline": saturated_fats_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
    else:
        # Calculate how much excess it is
        excess_saturated_fats = saturated_fats_per_100g - saturated_fats_low
        remain_data.append(f"High in Saturated Fats: {excess_saturated_fats:.2f}g per 100g")

# __________________________________ PUFA __________________________________________________________________________________________________________________________________

     # Extract fatty acid values
    saturated_fats_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_saturated_fats")
    total_saturated_fats =  next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_saturated_fats")

    monounsaturated_fats_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_monounsaturated_fats")
    total_monounsaturated_fats = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_monounsaturated_fats")

    polyunsaturated_fats_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_polyunsaturated_fats")
    total_polyunsaturated_fats = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fatty_acid_profile"] if item["name"] == "total_polyunsaturated_fats")

    original_total_saturated_fats = total_saturated_fats
    original_total_monounsaturated_fats = total_monounsaturated_fats
    original_total_polyunsaturated_fats = total_polyunsaturated_fats

    total_saturated_fats = total_saturated_fats * unit_conversion.get(saturated_fats_unit, 1)
    total_monounsaturated_fats = total_monounsaturated_fats * unit_conversion.get(monounsaturated_fats_unit, 1)
    total_polyunsaturated_fats = total_polyunsaturated_fats * unit_conversion.get(polyunsaturated_fats_unit, 1)

    # Calculate total fatty acids
    total_fats = total_saturated_fats + total_monounsaturated_fats + total_polyunsaturated_fats

    original_total_polyunsaturated_fats_per_100g = (original_total_polyunsaturated_fats / serving_size) * 100

    total_polyunsaturated_fats_low_guideline = f"If at least 45% of the fatty acids come from Polyunsaturated Fatty Acids and provide more than 20% of total energy." 
    
    # Total energy
    total_energy = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["macro_nutrients"] if item["name"] == "energy")

    # Energy from PUFA (polyunsaturated fats)
    energy_from_pufa = total_polyunsaturated_fats * 9  # 1g PUFA = 9 kcal


    # Calculate percentage of PUFA in total fatty acids
    if total_fats != 0:
        pufa_percentage_in_fats = (total_polyunsaturated_fats / total_fats) * 100
    else:
        pufa_percentage_in_fats = 0

    # Calculate percentage of energy from PUFA
    if total_energy != 0:
        pufa_energy_percentage = (energy_from_pufa / total_energy) * 100
    else:
        pufa_energy_percentage = 0

    # Check if the dish qualifies as "PUFA High"
    if pufa_percentage_in_fats > 45 and pufa_energy_percentage > 20:
        tags.append("High in Polyunsaturated Fatty Acids")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "High in Polyunsaturated Fatty Acids",
                    "Name of Nutrients": "Polyunsaturated Fatty Acids",
                    "Value": total_polyunsaturated_fats,
                    "Unit": polyunsaturated_fats_unit,
                    "Convertion for claims" : round(original_total_polyunsaturated_fats_per_100g,2),
                    "Guideline": total_polyunsaturated_fats_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
    else:
    # If PUFA does not meet the high criteria, calculate how much it is short
      if pufa_percentage_in_fats < 45:
          pufa_fats_excess = 45 - pufa_percentage_in_fats
          remain_data.append(f"Polyunsaturated Fatty Acids is short by {pufa_fats_excess:.2f}% in total fatty acids")

      if pufa_energy_percentage < 20:
          pufa_energy_excess = 20 - pufa_energy_percentage
          remain_data.append(f"Polyunsaturated Fatty Acids energy is short by {pufa_energy_excess:.2f}% of total energy")

# __________________________________ MUFA ___________________________________________________________________________________________________________________________________

    # Extract individual fatty acid values
    total_fatty_acids = total_saturated_fats + total_monounsaturated_fats + total_polyunsaturated_fats
    
    # Convert MUFA to kcal (1 g of fat = 9 kcal)
    mufa_energy = (total_monounsaturated_fats) * 9  # converting mg to g and multiplying by kcal/g
    
    total_monosaturated_fats_per_100g = (total_monounsaturated_fats / serving_size) * 100
    original_total_monosaturated_fats_per_100g = (original_total_monounsaturated_fats / serving_size) * 100
    
    monosaturated_fats_high_guideline = f"If at least 45% of the fatty acids come from Monosaturated Fatty Acids and provide more than 20% of total energy."

    # Calculate MUFA percentage and energy contribution
    if total_fatty_acids != 0:
        mufa_percentage = (total_monounsaturated_fats / total_fatty_acids) * 100
    else:
        mufa_percentage = 0

    if total_energy != 0:
        mufa_energy_contribution = (mufa_energy / total_energy) * 100
    else:
        mufa_energy_contribution = 0

    if mufa_percentage > 45 and mufa_energy_contribution > 20:
      tags.append("High in Monosaturated Fatty Acids")
      details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "High in Monosaturated Fatty Acids",
                    "Name of Nutrients": "Monosaturated Fatty Acids",
                    "Value": total_monounsaturated_fats,
                    "Unit": monounsaturated_fats_unit,
                    "Convertion for claims" : round(original_total_monosaturated_fats_per_100g,2),
                    "Guideline": monosaturated_fats_high_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
    else:
      # If MUFA does not meet the high criteria, calculate the shortfall or how close it is
      if mufa_percentage < 45:
          mufa_percentage_shortfall = 45 - mufa_percentage
          remain_data.append(f"Monosaturated Fatty Acids is short by {mufa_percentage_shortfall:.2f}% in total fatty acids")
      else:
          mufa_percentage_excess = mufa_percentage - 45
          remain_data.append(f"Monosaturated Fatty Acids exceeds by {mufa_percentage_excess:.2f}% in total fatty acids")

      if mufa_energy_contribution < 20:
          mufa_energy_shortfall = 20 - mufa_energy_contribution
          remain_data.append(f"Monosaturated Fatty Acids energy is short by {mufa_energy_shortfall:.2f}% of total energy")
      else:
          mufa_energy_excess = mufa_energy_contribution - 20
          remain_data.append(f"Monosaturated Fatty Acids energy exceeds by {mufa_energy_excess:.2f}% of total energy")

#__________________________________ Unsaturated Fat ___________________________________________________________________________________________________________________________

    # Energy from Unsaturated Fats (Monounsaturated + Polyunsaturated fats)
    unsaturated_fats = total_monounsaturated_fats + total_polyunsaturated_fats
    
    energy_from_unsaturated_fats = unsaturated_fats * 9  # 1g unsaturated fats = 9 kcal
    
    total_unsaturated_fats_per_100g = (unsaturated_fats / serving_size) * 100
    
    unsaturated_fats_high_guideline = f"If at least 70% of the fatty acids come from unsaturated fat and provide more than 20% of total energy."

    # Calculate percentage of unsaturated fats in total fatty acids
    if total_fats != 0:
        unsaturated_percentage_in_fats = (unsaturated_fats / total_fats) * 100
    else:
        unsaturated_percentage_in_fats = 0

    # Calculate percentage of energy from unsaturated fats
    if total_energy != 0:
        unsaturated_energy_percentage = (energy_from_unsaturated_fats / total_energy) * 100
    else:
        unsaturated_energy_percentage = 0

    # Check if the dish qualifies as "Unsaturated Fat High"
    if unsaturated_percentage_in_fats > 70 and unsaturated_energy_percentage > 20:
        tags.append("High in Unsaturated Fats")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "High in Unsaturated Fatty Acids",
                    "Name of Nutrients": "Unsaturated Fatty Acids",
                    "Value": unsaturated_fats,
                    "Unit": monounsaturated_fats_unit, # Assuming the same unit for both MUFA and PUFA
                    "Convertion for claims" : round(total_unsaturated_fats_per_100g,2),
                    "Guideline": unsaturated_fats_high_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })       
    else:
        # Detailed analysis for Unsaturated Fat shortfall or excess
        if unsaturated_percentage_in_fats < 70:
            unsaturated_percentage_shortfall = 70 - unsaturated_percentage_in_fats
            remain_data.append(f"Unsaturated fats are short by {unsaturated_percentage_shortfall:.2f}% in total fatty acids")
        else:
            unsaturated_percentage_excess = unsaturated_percentage_in_fats - 70
            remain_data.append(f"Unsaturated fats exceed by {unsaturated_percentage_excess:.2f}% in total fatty acids")

        if unsaturated_energy_percentage < 20:
            unsaturated_energy_shortfall = 20 - unsaturated_energy_percentage
            remain_data.append(f"Energy from unsaturated fats is short by {unsaturated_energy_shortfall:.2f}% of total energy")
        else:
            unsaturated_energy_excess = unsaturated_energy_percentage - 20
            remain_data.append(f"Energy from unsaturated fats exceeds by {unsaturated_energy_excess:.2f}% of total energy")

#________________________________ Trans Fat ____________________________________________________________________________________________________________________________________

    fat = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["macro_nutrients"] if item["name"] == "fats")
    fat_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["macro_nutrients"] if item["name"] == "fats")
    fat = fat * unit_conversion.get(fat_unit, 1)
    
    trans_fat_low_guideline = "If it contains less than 0.2 g per 100 grams." if unit == "g" else "If it contains less than 1 g per 100 ml."

    # Calculate Trans Fat
    trans_fat = fat - total_fats
    trans_fat = round(trans_fat, 2)
    if trans_fat > 0:

        trans_fat_per_100ml = trans_fat / serving_size * 100

        if trans_fat_per_100ml < 0.2:
            tags.append("Trans Fats Free")
            details_of_claims.append({
                        "Sr no": len(details_of_claims) + 1,
                        "Claim Words": "Trans Fats Free",
                        "Name of Nutrients": "Trans Fats",
                        "Value": trans_fat,
                        "Unit": fat_unit,
                        "Convertion for claims" : round(trans_fat_per_100ml,2),
                        "Guideline": trans_fat_low_guideline,
                        "Referance" : fassi_guidelines,
                        "Results": "Pass"
                    })        
        else:
            trans_fat_excess = trans_fat_per_100ml - 0.2
            remain_data.append(f"Trans fat exceeds the limit by {trans_fat_excess:.2f}g per 100ml")


#__________________________________ Cholesterol _______________________________________________________________________________________________________________________________

    cholesterol_low = 0.02 if unit == "g" else 0.01 # in gram
    cholesterol_free = 0.005 # in gram
    saturated_fats_cholesterol = 1500 if unit == "g" else 750 # in gram

    cholesterol_free_guideline = "If it has 5 mg or less of cholesterol per 100 grams. And if saturated fat does not exceed 1.5 g per 100 g." if unit == "g" else "If it has 5 mg or less of cholesterol per 100 ml. And if saturated fat does not exceed 0.75 g per 100 ml."
    cholesterol_low_guideline = "If it has 20 mg or less of cholesterol and 1.5 g or less of saturated fat per 100 grams." if unit == "g" else "If it has 10 mg or less of cholesterol and 0.75 g or less of saturated fat per 100 ml."

    cholesterol_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["cholesterol"] if item["name"] == "cholesterol")
    cholesterol = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["cholesterol"] if item["name"] == "cholesterol")
    original_cholesterol = cholesterol
    cholesterol = cholesterol * unit_conversion.get(cholesterol_unit, 1)

    Cholesterol_per_100g = ( original_cholesterol / serving_size) * 100

    if Cholesterol_per_100g < cholesterol_free and saturated_fats_per_100g < saturated_fats_cholesterol:
        tags.append("Cholesterol Free")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Cholesterol Free",
                    "Name of Nutrients": "Cholesterol",
                    "Value": original_cholesterol,
                    "Unit": cholesterol_unit,
                    "Convertion for claims" : round(Cholesterol_per_100g,2),
                    "Guideline": cholesterol_free_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
    elif Cholesterol_per_100g < cholesterol_low and saturated_fats_per_100g < saturated_fats_cholesterol:
        tags.append("Low in Cholesterol")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Low in Cholesterol",
                    "Name of Nutrients": "Cholesterol",
                    "Value": original_cholesterol,
                    "Unit": cholesterol_unit,
                    "Convertion for claims" : round(Cholesterol_per_100g,2),
                    "Guideline": cholesterol_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
    else:
      cholesterol_excess = Cholesterol_per_100g - cholesterol_low
      remain_data.append(f"Cholesterol exceeds the low limit by {cholesterol_excess:.2f}mg per 100g or 100ml")

#________________________________ Sugar _______________________________________________________________________________________________________________________________________

    total_sugars = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["sugar"] if item["name"] == "total_free_sugars")
    sugar_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["sugar"] if item["name"] == "total_free_sugars")
    suger_free = 0.5 #in gram
    suger_low = 5 if unit == "g" else 2.5 #in gram
    original_sugars = total_sugars
    suger_low = 5 if unit == "g" else 2.5 #in gram
    total_sugars = total_sugars * unit_conversion.get(sugar_unit, 1)
    sugars_low_guideline = "If it contains no more than 5 g per 100 grams." if unit == "g" else "If it contains no more than 2.5 g per 100 ml."
    sugars_free_guideline = "If it contains no more than 0.5 g per 100 grams." if unit == "g" else "If it contains no more than 0.5 g per 100 ml."

    if unit == 'ml':
        # Liquid: Check if the sugars are < 2.5g per 100ml
        sugars_per_100ml = total_sugars / serving_size * 100
        if sugars_per_100ml < suger_free:
            tags.append("Sugars Free")
            details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Sugars Free",
                    "Name of Nutrients": "Sugars",
                    "Value": original_sugars,
                    "Unit": sugar_unit,
                    "Convertion for claims" : round(sugars_per_100ml,2),
                    "Guideline": sugars_free_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
        elif sugars_per_100ml < suger_low:
            tags.append("Low in Sugars")
            details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Low in Sugars",
                    "Name of Nutrients": "Sugars",
                    "Value": original_sugars,
                    "Unit": sugar_unit,
                    "Convertion for claims" : round(sugars_per_100ml,2),
                    "Guideline": sugars_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
        else:
            sugars_excess = sugars_per_100ml - 2.5
            remain_data.append(f"Sugars exceed the low limit by {sugars_excess:.2f}g per 100ml")

    elif unit == 'g':
        # Solid: Check if the sugars are < 5g per 100g
        sugars_per_100g = total_sugars / serving_size * 100
        if sugars_per_100g < suger_free:
            tags.append("Sugars Free")
            details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Sugars Free",
                    "Name of Nutrients": "Sugars",
                    "Value": original_sugars,
                    "Unit": sugar_unit,
                    "Convertion for claims" : round(sugars_per_100g,2),
                    "Guideline": sugars_free_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
        elif sugars_per_100g < suger_low:
            tags.append("Low in Sugars")
            details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Low in Sugars",
                    "Name of Nutrients": "Sugars",
                    "Value": original_sugars,
                    "Unit": sugar_unit,
                    "Convertion for claims" : round(sugars_per_100g,2),
                    "Guideline": sugars_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
        else:
            sugars_excess = sugars_per_100g - 5
            remain_data.append(f"Sugars exceed the low limit by {sugars_excess:.2f}g per 100g")


#________________________________ macro_nutrients ______________________________________________________________________________________________________________________________

    # energy limits
    energy_low = 40 if unit == "g" else 20
    energy_free = 0 if unit == "g" else 4

    energy_free_guideline = "If it has 4 kcal or less per 100 grams." if unit == "g" else "If it has 4 kcal or less per 100 ml."
    energy_low_guideline = "If it has 40 kcal or less per 100 grams." if unit == "g" else "If it has 20 kcal or less per 100 ml."

    # fats limits
    fats_low = 3 if unit == "g" else 1.5
    fats_free = 0.5
    fats_free_guideline = "If it has 0.5 g or less per 100 grams." if unit == "g" else "If it has 0.5 g or less per 100 ml."
    fats_low_guideline = "If it has 3 g or less per 100 grams." if unit == "g" else "If it has 1.5 g or less per 100 ml."

    # proteins limits
    rda_protein = rda_values["proteins"]
    proteins_high = 0.2 * rda_protein if unit == "g" else 0.1 * rda_protein
    proteins_source = 0.1 * rda_protein if unit == "g" else 0.05 * rda_protein
    proteins_high_guideline = "If it provides at least 10.8 g of the RDA per 100 grams." if unit == "g" else "If it provides at least 5.4 g of the RDA per 100 ml."
    proteins_source_guideline = "If it provides at least 5.4 g per 100 grams." if unit == "g" else "If it provides at least 2.7 g per 100 ml."

    # fibre limits
    fibre_high = 6
    fibre_high_kcal = 3
    fibre_source = 3
    fibre_source_kcal = 1.5
    fibre_high_guideline = "If it contains at least 6 g per 100 grams." if unit == "g" else "If it contains at least 6 g per 100 ml."
    fibre_source_guideline = "If it contains at least 3 g per 100 grams." if unit == "g" else "If it contains at least 3 g per 100 ml."
    fibre_high_kcal_guideline = "If it contains at least 3 g per 100 kcal."
    fibre_source_kcal_guideline = "If it contains at least 1.5 g per 100 kcal."

    for nutrient in data["dish_variants"]["normal"]["full"]["calculate_nutrients"].get("macro_nutrients", []):

        # Convert nutrient value to grams if needed
        nutrient_unit = nutrient.get("unit", "g").lower()
        original_nutrient_value = nutrient["value"]
        nutrient_value_in_grams = nutrient["value"] * unit_conversion.get(nutrient_unit, 1)

        if nutrient["name"] == "energy":

            energy_per_100g = (nutrient_value_in_grams / serving_size) * 100

            if energy_per_100g < energy_free:
                tags.append("Energy Free")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Energy Free",
                    "Name of Nutrients": "Energy",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(energy_per_100g,2),
                    "Guideline": energy_free_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif energy_per_100g < energy_low:
                tags.append("Low in Energy")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Low in Energy",
                    "Name of Nutrients": "Energy",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(energy_per_100g,2),
                    "Guideline": energy_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            else:
                energy_excess = energy_per_100g - energy_low
                remain_data.append(f"Energy exceeds the low limit by {energy_excess:.2f} kcal per 100{unit}")

        if nutrient["name"] == "fats":
            fats_per_100g = (nutrient_value_in_grams / serving_size) * 100
            if fats_per_100g < fats_free:
                tags.append("Fats Free")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Fats Free",
                    "Name of Nutrients": "Fats",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(fats_per_100g,2),
                    "Guideline": fats_free_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif fats_per_100g < fats_low:
                tags.append("Low in Fats")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Low in Fats",
                    "Name of Nutrients": "Fats",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(fats_per_100g,2),
                    "Guideline": fats_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            else:
              fats_excess = fats_per_100g - fats_low
              remain_data.append(f"Fats exceed the low limit by {fats_excess:.2f}g per 100{unit}")

        if nutrient["name"] == "proteins":
            proteins_per_100g = (nutrient_value_in_grams / serving_size) * 100
            if proteins_per_100g > proteins_high:
                tags.append("High in Proteins")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "High in Proteins",
                    "Name of Nutrients": "Proteins",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(proteins_per_100g,2),
                    "Guideline": proteins_high_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif proteins_per_100g > proteins_source:
                tags.append("Contains Proteins")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Contains Proteins",
                    "Name of Nutrients": "Proteins",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(proteins_per_100g,2),
                    "Guideline": proteins_source_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            else:
                proteins_deficit = proteins_source - proteins_per_100g
                remain_data.append(f"Proteins are below the source limit by {proteins_deficit:.2f}g per 100{unit}")


        if nutrient["name"] == "fibers":
            fibers_per_100g = (nutrient_value_in_grams / serving_size) * 100
            fiber_per_100kcal = (fibers_per_100g / total_energy) * 100 if total_energy > 0 else 0

            if fibers_per_100g > fibre_high:
                tags.append("High in Fibers")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "High in Fibers",
                    "Name of Nutrients": "Fibers",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(fibers_per_100g,2),
                    "Guideline": fibre_high_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif fiber_per_100kcal > fibre_high_kcal:
                tags.append("High in Fibers")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "High in Fibers",
                    "Name of Nutrients": "Fibers",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(fibers_per_100g,2),
                    "Guideline": fibre_high_kcal_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif fibers_per_100g > fibre_source:
                tags.append("Contains Fibers")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Contains Fibers",
                    "Name of Nutrients": "Fibers",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(fibers_per_100g,2),
                    "Guideline": fibre_source_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif fiber_per_100kcal > fibre_source_kcal:
                tags.append("Contains Fibers")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Contains Fibers",
                    "Name of Nutrients": "Fibers",
                    "Value": original_nutrient_value,
                    "Unit": nutrient_unit,
                    "Convertion for claims" : round(fibers_per_100g,2),
                    "Guideline": fibre_source_kcal_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            else:
                fibers_deficit = fibre_source - fibers_per_100g
                remain_data.append(f"Fibers are below the source limit by {fibers_deficit:.2f}g per 100{unit}")

#______________________________ sodium _______________________________________________________________________________________________________________________________________

    # Sodium limits
    sodium_free = 5 #mg
    sodium_very_low = 40 # mg
    sodium_low = 120 # mg
    sodium_free_guideline = "If it has 5 mg or less of sodium per 100 grams." if unit == "g" else "If it has 5 mg or less of sodium per 100 ml."
    sodium_low_guideline = "If it has 120 mg or less of sodium per 100 grams." if unit == "g" else "If it has 120 mg or less of sodium per 100 ml."
    sodium_very_low_guideline = "If it has 40 mg or less of sodium per 100 grams." if unit == "g" else "If it has 40 mg or less of sodium per 100 ml."

    for nutrient in data["dish_variants"]["normal"]["full"]["calculate_nutrients"].get("minerals", []):

        if nutrient["name"] == "sodium":

            sodium_unit = nutrient.get("unit").lower()
            sodium = nutrient["value"]
            sodium_per_100g = ((sodium / serving_size) * 100)

            if sodium_per_100g < sodium_free:
                tags.append("Sodium Free")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Sodium Free",
                    "Name of Nutrients": "Sodium",
                    "Value": sodium,
                    "Unit": sodium_unit,
                    "Convertion for claims" : round(sodium_per_100g,2),
                    "Guideline": sodium_free_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif sodium_per_100g < sodium_very_low:
                tags.append("Very Low in Sodium")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Very Low in Sodium",
                    "Name of Nutrients": "Sodium",
                    "Value": sodium,
                    "Unit": sodium_unit,
                    "Convertion for claims" : round(sodium_per_100g,2),
                    "Guideline": sodium_very_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            elif sodium_per_100g < sodium_low:
                tags.append("Low in Sodium")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Sodium Free",
                    "Name of Nutrients": "Sodium",
                    "Value": sodium,
                    "Unit": sodium_unit,
                    "Convertion for claims" : round(sodium_per_100g,2),
                    "Guideline": sodium_low_guideline,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            else:
                # Calculate how much sodium exceeds the low threshold if it's above
                sodium_excess = sodium_per_100g - sodium_low
                remain_data.append(f"Sodium exceeds the low limit by {sodium_excess:.4f}g per 100{unit}")

#___________________________ Lactose ____________________________________________________________________________________________________________________________________

    if not any(any(lactose_word in ing["name"].lower() for lactose_word in lactose_ingredients)
           for ing in data["dish_variants"]["normal"]["full"]["ingredients"]):
        tags.append("Lactose Free")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Lactose Free",
                    "Name of Nutrients": "Lactose",
                    "Value": "N/A",
                    "Unit": "N/A",
                    "Convertion for claims" : "N/A",
                    "Guideline": "If the lactose content does not exceed 0.1%.",
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })

#___________________________ Gluten ______________________________________________________________________________________________________________________________________

    if not any(any(gluten_word in ing["name"].lower() for gluten_word in gluten_ingredients)
           for ing in data["dish_variants"]["normal"]["full"]["ingredients"]):
        tags.append("Gluten Free")
        details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Gluten Free",
                    "Name of Nutrients": "Gluten",
                    "Value": "N/A",
                    "Unit": "N/A",
                    "Convertion for claims" : "N/A",
                    "Guideline": "If the gluten content does not exceed 20 mg per kg.",
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })

#_____________________________ Vitamin K ________________________________________________________________________________________________________________________________________

    contains_threshold = 15 if unit == "g" else 7.5
    high_threshold = 30 if unit == "g" else 15

    vitamin_k1_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_k1")
    vitamin_k1_value = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_k1")
    vitamin_k2_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_k2")
    vitamin_k2_value = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_k2")
    vitamin_k = vitamin_k1_value + vitamin_k2_value
    vitamin_k_per_100g = ((vitamin_k / serving_size) * 100)

    high_condition_vitk = f"If it provides at least {round((rda_values['vitamin_k'] * high_threshold)/100, 2)} {vitamin_k1_unit} per 100 {unit} for Vitamin K."
    contains_condition_vitk = f"If it provides at least {round((rda_values['vitamin_k'] * contains_threshold)/100, 2)} {vitamin_k1_unit} per 100 {unit} for Vitamin K."

    percentage = 0
    if unit.lower() == "ml":
        if vitamin_k != 0:
            percentage = (vitamin_k_per_100g / rda_values["vitamin_k"]) * 100
            if percentage > 7.5:
                if percentage > 15:
                    tags.append(f"High in Vitamin K")
                    details_of_claims.append({
                        "Sr no": len(details_of_claims) + 1,
                        "Claim Words": "High in Vitamin K",
                        "Name of Nutrients": "Vitamin K",
                        "Value": vitamin_k,
                        "Unit": vitamin_k1_unit,
                        "Convertion for claims" : round(vitamin_k_per_100g,2),
                        "Guideline": high_condition_vitk,
                        "Referance" : fassi_guidelines,
                        "Results": "Pass"
                    })
                else:
                    tags.append(f"Contains Vitamin K")
                    details_of_claims.append({
                        "Sr no": len(details_of_claims) + 1,
                        "Claim Words": "Contains Vitamin K",
                        "Name of Nutrients": "Vitamin K",
                        "Value": vitamin_k,
                        "Unit": vitamin_k1_unit,
                        "Convertion for claims" : round(vitamin_k_per_100g,2),
                        "Guideline": contains_condition_vitk,
                        "Referance" : fassi_guidelines,
                        "Results": "Pass"
                    })
            else:
                remaining_percentage = 7.5 - percentage
                remain_data.append(f"Vitamin K lack by: {remaining_percentage:.2f}% of RDA")

    elif unit.lower() == "g":
        percentage = (vitamin_k_per_100g / rda_values["vitamin_k"]) * 100
        if percentage > 15:
            if percentage > 30:
                tags.append(f"High in Vitamin K")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "High in Vitamin K",
                    "Name of Nutrients": "Vitamin K",
                    "Value": vitamin_k,
                    "Unit": vitamin_k1_unit,
                    "Convertion for claims" : round(vitamin_k_per_100g,2),
                    "Guideline": high_condition_vitk,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
            else:
                tags.append(f"Contains Vitamin K")
                details_of_claims.append({
                    "Sr no": len(details_of_claims) + 1,
                    "Claim Words": "Contains Vitamin K",
                    "Name of Nutrients": "Vitamin K",
                    "Value": vitamin_k,
                    "Unit": vitamin_k1_unit,
                    "Convertion for claims" : round(vitamin_k_per_100g,2),
                    "Guideline": contains_condition_vitk,
                    "Referance" : fassi_guidelines,
                    "Results": "Pass"
                })
        else:
            remaining_percentage = 15 - percentage
            remain_data.append(f"Vitamin K lack by: {remaining_percentage:.2f}% of RDA")

#_____________________________ Vitamin D ________________________________________________________________________________________________________________________________________

    vitamin_d2_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_d2")
    vitamin_d2_value = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_d2") * unit_conversion.get(vitamin_d2_unit, 1)
    vitamin_d3_unit = next(item["unit"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_d3")
    vitamin_d3_value = next(item["value"] for item in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["fat_soluble_vitamin"] if item["name"] == "vitamin_d3") * unit_conversion.get(vitamin_d3_unit, 1)
    vitamin_d = vitamin_d2_value + vitamin_d3_value
    vitamin_d_per_100g = ((vitamin_d / serving_size) * 100)
    high_condition_vitd = f"If it provides at least {round((rda_values['vitamin_d'] * high_threshold)/100, 3)} {vitamin_d2_unit} per 100 {unit} for Vitamin K."
    contains_condition_vitd = f"If it provides at least {round((rda_values['vitamin_d'] * contains_threshold)/100, 3)} {vitamin_d2_unit} per 100 {unit} for Vitamin K."

    percentage = 0

    if max_limits['vitamin_d'] > vitamin_d:

        if unit.lower() == "ml":
            if vitamin_d != 0:
                percentage = (vitamin_d_per_100g / rda_values["vitamin_d"]) * 100
                if percentage > 7.5:
                    if percentage > 15:
                        tags.append(f"High in Vitamin D")
                        details_of_claims.append({
                            "Sr no": len(details_of_claims) + 1,
                            "Claim Words": "High in Vitamin D",
                            "Name of Nutrients": "Vitamin D",
                            "Value": vitamin_d,
                            "Unit": vitamin_d2_unit,
                            "Convertion for claims" : round(vitamin_d_per_100g,2),
                            "Guideline": high_condition_vitd,
                            "Referance" : fassi_guidelines,
                            "Results": "Pass"
                        })
                    else:
                        tags.append(f"Contains Vitamin D")
                        details_of_claims.append({
                            "Sr no": len(details_of_claims) + 1,
                            "Claim Words": "Contains Vitamin D",
                            "Name of Nutrients": "Vitamin D",
                            "Value": vitamin_d,
                            "Unit": vitamin_d2_unit,
                            "Convertion for claims" : round(vitamin_d_per_100g,2),
                            "Guideline": contains_condition_vitd,
                            "Referance" : fassi_guidelines,
                            "Results": "Pass"
                        })
                else:
                    remaining_percentage = 7.5 - percentage
                    remain_data.append(f"Vitamin K lack by: {remaining_percentage:.2f}% of RDA")

        elif unit.lower() == "g":
            percentage = (vitamin_d_per_100g / rda_values["vitamin_d"]) * 100
            if percentage > 15:
               if percentage > 30:
                    tags.append(f"High in Vitamin D")
                    details_of_claims.append({
                        "Sr no": len(details_of_claims) + 1,
                        "Claim Words": "High in Vitamin D",
                        "Name of Nutrients": "Vitamin D",
                        "Value": vitamin_d,
                        "Unit": vitamin_d2_unit,
                        "Convertion for claims" : round(vitamin_d_per_100g,2),
                        "Guideline": high_condition_vitd,
                        "Referance" : fassi_guidelines,
                        "Results": "Pass"
                    })
               else:
                    tags.append(f"Contains Vitamin D")
                    details_of_claims.append({
                        "Sr no": len(details_of_claims) + 1,
                        "Claim Words": "Contains Vitamin D",
                        "Name of Nutrients": "Vitamin D",
                        "Value": vitamin_d,
                        "Unit": vitamin_d2_unit,
                        "Convertion for claims" : round(vitamin_d_per_100g,2),
                        "Guideline": contains_condition_vitd,
                        "Referance" : fassi_guidelines,
                        "Results": "Pass"
                    })
            else:
                remaining_percentage = 15 - percentage
                remain_data.append(f"Vitamin D lack by: {remaining_percentage:.2f}% of RDA")

    # Function to format and replace names
    def format_and_replace(phrase):
        # Check if the phrase matches "High in ..."/"Contains ..." and format accordingly
        phrase = re.sub(
            r"(High in|Contains) (\w+)",
            lambda match: f"{match.group(1)} {replacement_map.get(match.group(2), match.group(2).capitalize())}",
            phrase
        )
        # If it's a single word or doesn't match the "High in" pattern, handle normally
        words = phrase.split('_')
        return ' '.join(
            replacement_map.get(word, word.capitalize()) if word.isalpha() else word
            for word in words
        )
#_______________________________ minerals, vitamins ___________________________________________________________________________________________________________________________

    for category in ['water_soluble_vitamin', 'fat_soluble_vitamin', 'minerals']:
        for nutrient in data["dish_variants"]["normal"]["full"]["calculate_nutrients"][category]:
            nutrient_name = nutrient["name"]
            nutrient_value = nutrient["value"]
            nutrient_original_value = nutrient_value
            nutrient_unit = nutrient["unit"]

            if nutrient_name in rda_values:
                rda_value = rda_values[nutrient_name]
            else:
                continue
            
            if nutrient_name in max_limits:
                max_limit = max_limits[nutrient_name]
                if max_limit < nutrient_value:
                    continue

            nutrient_per_100g = ((nutrient_original_value / serving_size) * 100)

            high_condition = f"If it provides at least {round((rda_values[nutrient_name] * high_threshold)/100, 3)} {nutrient_unit} per 100 {unit} for {format_and_replace(nutrient_name)}."
            conatains_condition = f"If it provides at least {round((rda_values[nutrient_name] * contains_threshold)/100, 3)} {nutrient_unit} per 100 {unit} for {format_and_replace(nutrient_name)}."

            formated_nutrient_name = format_and_replace(nutrient_name)
            #nutrient_value = (nutrient_value * unit_conversion.get(nutrient_unit.lower(), 1) / serving_size) * 100

            percentage = 0
            if unit.lower() == "ml":
                if nutrient_value != 0:
                    percentage = (nutrient_per_100g / rda_value) * 100
                    if percentage > 7.5:
                        if percentage > 15:
                            tags.append(f"High in {formated_nutrient_name}")
                            details_of_claims.append({
                                "Sr no": len(details_of_claims) + 1,
                                "Claim Words": f"High in {formated_nutrient_name}",
                                "Name of Nutrients": formated_nutrient_name,
                                "Value": nutrient_original_value,
                                "Unit": nutrient_unit,
                                "Convertion for claims" : round(nutrient_per_100g,2),
                                "Guideline": high_condition,
                                "Referance" : fassi_guidelines,
                                "Results": "Pass"
                            })
                        else:
                            tags.append(f"Contains {formated_nutrient_name}")
                            details_of_claims.append({
                                "Sr no": len(details_of_claims) + 1,
                                "Claim Words": f"High in {formated_nutrient_name}",
                                "Name of Nutrients": formated_nutrient_name,
                                "Value": nutrient_original_value,
                                "Unit": nutrient_unit,
                                "Convertion for claims" : round(nutrient_per_100g,2),
                                "Guideline": conatains_condition,
                                "Referance" : fassi_guidelines,
                                "Results": "Pass"
                            })
                else:
                    remaining_percentage = 7.5 - percentage
                    remain_data.append(f"{nutrient_name} lack by: {remaining_percentage:.2f}% of RDA")

            elif unit.lower() == "g":
                if nutrient_value != 0:
                    percentage = (nutrient_per_100g / rda_value) * 100
                    if percentage > 15:
                        if percentage > 30:
                            tags.append(f"High in {formated_nutrient_name}")
                            details_of_claims.append({
                                "Sr no": len(details_of_claims) + 1,
                                "Claim Words": f"High in {formated_nutrient_name}",
                                "Name of Nutrients": formated_nutrient_name,
                                "Value": nutrient_original_value,
                                "Unit": nutrient_unit,
                                "Convertion for claims" : round(nutrient_per_100g,2),
                                "Guideline": high_condition,
                                "Referance" : fassi_guidelines,
                                "Results": "Pass"
                            })
                        else:
                            tags.append(f"Contains {formated_nutrient_name}")
                            details_of_claims.append({
                                "Sr no": len(details_of_claims) + 1,
                                "Claim Words": f"Contains {formated_nutrient_name}",
                                "Name of Nutrients": formated_nutrient_name,
                                "Value": nutrient_original_value,
                                "Unit": nutrient_unit,
                                "Convertion for claims" : round(nutrient_per_100g,2),
                                "Guideline": conatains_condition,
                                "Referance" : fassi_guidelines,
                                "Results": "Pass"
                            })
                    else:
                        remaining_percentage = 15 - percentage
                        remain_data.append(f"{nutrient_name} lack by: {remaining_percentage:.2f}% of RDA")

    import_nutrients_tags = ["proteins","energy","PUFA","thiamin","riboflavin","niacin","biotin","vitamin_b5","vitamin_b6","vitamin_c","folate","vitamin_a","vitamin_d","Calcium","Iron","Magnesium","Potassium","Zinc","Selenium","vitamin_e","carotenoids","Fiber" ]

    main_food_claims = []
    lack_of_nutrients_data = []
    less_important_claims = []

    # Process output_list
    for item in tags:
        if "Contains" in item:
            # Extract nutrient name after "Contains"
            nutrient = item.split("Contains")[1].strip()
            if nutrient not in import_nutrients_tags:
                less_important_claims.append(item)  # Move to other list
            else:
                main_food_claims.append(item)  # Keep in filtered list
        else:
            main_food_claims.append(item)  # Keep non-"Contains" strings as is

    final_details_of_claims = []
    # Process output_list
    for item in details_of_claims:
        if "Contains" in item["Claim Words"]:
            # Extract nutrient name after "Contains"
            nutrient = item["Claim Words"].split("Contains")[1].strip()
            if nutrient in import_nutrients_tags:               
                final_details_of_claims.append(item)  # Keep in filtered list
        else:
            final_details_of_claims.append(item)  # Keep non-"Contains" strings as is

    remain_data = [s.replace("-", "") for s in remain_data]
    main_food_claims = list(dict.fromkeys(main_food_claims))

    return main_food_claims ,less_important_claims, remain_data, final_details_of_claims


