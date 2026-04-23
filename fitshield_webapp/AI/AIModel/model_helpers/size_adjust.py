import copy

def adjust_serving_size(dish_info, new_serving_size):
    if not isinstance(dish_info, dict):
        raise ValueError("dish_info must be a dictionary.")
    if not isinstance(new_serving_size, (int, float)) or new_serving_size <= 0:
        raise ValueError("new_serving_size must be a positive number.")

    # Copy the original dish info to avoid mutating the input
    updated_dish_info = copy.deepcopy(dish_info)

    # Handle missing 'serving' field by providing a default
    if 'serving' not in updated_dish_info:
        updated_dish_info['serving'] = {
            "size": 200,  # Default size
            "unit": "g"   # Default unit
        }

    # Extract the old serving size
    try:
        old_serving_size = float(updated_dish_info['serving']['size'])
    except (KeyError, ValueError) as e:
        raise ValueError("Invalid or missing serving size in the dish information.") from e

    # Update the serving size
    updated_dish_info['serving']['size'] = new_serving_size

    # Validate and update ingredient quantities
    if 'ingredients' not in updated_dish_info or not isinstance(updated_dish_info['ingredients'], list):
        raise ValueError("Ingredients key is missing or not a list.")

    for ingredient in updated_dish_info['ingredients']:
        try:
            old_quantity = float(ingredient['quantity'])
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid or missing quantity for ingredient: {ingredient.get('name', 'Unknown')}") from e

        new_quantity = (new_serving_size * old_quantity) / old_serving_size
        ingredient['quantity'] = float(round(new_quantity, 2))

    return updated_dish_info
