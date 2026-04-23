import json

from fitshield_webapp.view.restro.save_json import save_json_to_file

def calculate_nutrient_energy_distribution(data):
    total_energy = next(
        nutrient["value"]  #error can be here
        for nutrient in data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["macro_nutrients"]
        if nutrient["name"] == "energy"
    )

    # Unit conversion for different nutrient units
    unit_conversion = {
        "g": 1,
        "kg": 1000,
        "mg": 0.001,
        "µg": 0.000001,
    }
    # Nutrient quantities
    macro_nutrients = data["dish_variants"]["normal"]["full"]["calculate_nutrients"]["macro_nutrients"]
    protein = next(nutrient["value"] for nutrient in macro_nutrients if nutrient["name"] == "proteins")
    protein_unit = next(nutrient["unit"] for nutrient in macro_nutrients if nutrient["name"] == "proteins")

    carbs = next(nutrient["value"] for nutrient in macro_nutrients if nutrient["name"] == "carbs")
    carbs_unit = next(nutrient["unit"] for nutrient in macro_nutrients if nutrient["name"] == "carbs")

    fats = next(nutrient["value"] for nutrient in macro_nutrients if nutrient["name"] == "fats")
    fats_unit = next(nutrient["unit"] for nutrient in macro_nutrients if nutrient["name"] == "fats")

    fiber = next(nutrient["value"] for nutrient in macro_nutrients if nutrient["name"] == "fibers")
    fiber_unit = next(nutrient["unit"] for nutrient in macro_nutrients if nutrient["name"] == "fibers")

    # Caloric values per gram for each nutrient
    caloric_values = {
        "proteins": 4,
        "carbs": 4,
        "fats": 9,
        "fibers": 2,
    }

    # Calculate energy contributions
    energy_contributions = {
        "proteins": (protein * unit_conversion.get(protein_unit, 1)) * caloric_values["proteins"],
        "carbs": (carbs * unit_conversion.get(carbs_unit, 1)) * caloric_values["carbs"],
        "fats": (fats * unit_conversion.get(fats_unit, 1)) * caloric_values["fats"],
        "fibers": (fiber * unit_conversion.get(fiber_unit, 1)) * caloric_values["fibers"],
    }

    # Calculate total energy from nutrients
    total_nutrient_energy = sum(energy_contributions.values())

    # Calculate percentage difference between reported total energy and computed total energy
    total_energy_max = max(total_energy, total_nutrient_energy)
    if total_energy_max == 0:
        energy_difference_percentage = 0
    else:
        energy_difference_percentage = ((total_nutrient_energy - total_energy) / total_energy_max) * 100

    # Adjust total energy if the difference exceeds 5%
    if abs(energy_difference_percentage) >= 5:
        total_energy = total_nutrient_energy

    # Calculate percentage contributions for each nutrient
    percentage_contributions = {}
    # save_json_to_file(total_energy, "dishes_output", "total_energy.json" )

    for nutrient, energy in energy_contributions.items():
        if total_energy == 0:
            percentage = "0.00%"
        else:
            percentage = f"{(energy / total_energy) * 100:.2f}%"
        percentage_contributions[nutrient] = percentage

    return percentage_contributions



