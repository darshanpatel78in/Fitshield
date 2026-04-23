from django.shortcuts import render
from django.http import JsonResponse
from fitshield_webapp.utils.nutrients_search import suggest_food,search_food  

def index(request):
    return render(request, 'nutrition/index.html')

def get_food_suggestions(request):
    query = request.GET.get('query', '')  
    if not query:
        return JsonResponse({"error": "Missing query parameter."}) 
    
    suggestions = suggest_food(query)
    
    return JsonResponse({"suggestions": suggestions})

def get_nutrition(request):
    food_name = request.GET.get('food', '')
    weight = request.GET.get('weight', '')

    if not food_name or not weight:
        return JsonResponse({"error": "Missing food or weight input"})

    food_name_normalized = food_name.strip().lower()

    try:
        weight = float(weight)
    except ValueError:
        return JsonResponse({"error": "Invalid weight input"})

    food_data = search_food(food_name_normalized)
    if food_data is None:
        return JsonResponse({"error": f"{food_name} not found in the database."})

    nutrition = {}
    for key, value in food_data.items():
        if isinstance(value, (int, float)):
            nutrition[key] = round((value * weight) / 100, 2)

    return JsonResponse({"food": food_name, "weight": weight, "nutrition": nutrition})
