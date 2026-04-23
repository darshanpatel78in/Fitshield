def calculate_nutrient_percentages(tdee, age, gender, goal, weight):
    # print(tdee, age, gender, goal, weight)
    # Clamp age
    if age < 18:
        age = 18
    elif age > 60:
        age = 60

    # Default ranges (examples; fill in your real logic)
    protein_min, protein_max = 20, 25
    carbs_min,   carbs_max   = 50, 55
    fats_min,    fats_max    = 20, 25
    fiber = 25
    prot_g_low, prot_g_high = 1.4, 1.8

    # Interpolation factors for age
    if age > 40:
        age_range = (40, 60)
    else:
        age_range = (18, 40)

    delta_age = (age_range[1] - age_range[0]) or 1

    # Example minimal
    protein_factor   = (protein_max - protein_min)/delta_age
    protein_g_factor = (prot_g_high - prot_g_low)/delta_age
    carbs_factor     = (carbs_max - carbs_min)/delta_age
    fats_factor      = (fats_max  - fats_min )/delta_age

    protein_percentage = protein_min + ( (age - age_range[0]) * protein_factor )
    protein_g_calc     = prot_g_low + ( (age - age_range[0]) * protein_g_factor )
    carbs_percentage   = carbs_max - ( (age - age_range[0]) * carbs_factor )
    fats_percentage    = fats_min + ( (age - age_range[0]) * fats_factor )

    # Force protein
    proteink_kcal = (protein_percentage * tdee)/100
    bodyweight_protein_kcal = (weight * protein_g_calc)
    actual_protein_kcal = max(proteink_kcal, bodyweight_protein_kcal)

    actual_fats_kcal = (fats_percentage * tdee)/100
    total_fiber_kcal = fiber * 2

    carbs_kcal = tdee - (total_fiber_kcal + actual_protein_kcal + actual_fats_kcal)

    final_prot_pct = (actual_protein_kcal/tdee)*100
    final_fats_pct = (actual_fats_kcal   /tdee)*100
    final_carbs_pct= (carbs_kcal         /tdee)*100

    return {
        "Protein (%)": round(final_prot_pct, 2),
        "Carbohydrates (%)": round(final_carbs_pct, 2),
        "Fats (%)": round(final_fats_pct, 2),
        "Fiber (g/day)": round(fiber * 2, 2)
    }