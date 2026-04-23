import logging

def remove_swapped_item_essential_category(ai_data):

    categories = ai_data.get("categories", {})
    essential_set = set(categories.get("essential", []))

    try:
        for variant_data in ai_data.get("dish_variants", {}).values():
            for size_data in variant_data.values():
                ingredients = size_data.get("ingredients", [])

                for ingredient in ingredients:
                    if ingredient["name"] in essential_set:

                        # Make ingredient non-swappable
                        ingredient["is_swappable"] = False
                        ingredient.pop("swap_items", None)  # Remove swap_items if present

        # Update essential category with Pasta included
        ai_data["categories"]["essential"] = list(essential_set)

        logging.debug("Final essential category: %s", ai_data["categories"]["essential"])
    except Exception as e:
        logging.error("Error updating essential category: %s", str(e))
        raise

    return ai_data
