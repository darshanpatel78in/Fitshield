from datetime import date, datetime
import requests
from fitshield.settings import WEATHER_API_KEY, WEATHER_API_URL


def convert_height_to_cm(height, unit):
    try:
        if unit.lower() == "feet":
            feet, inches = map(float, height.split("'"))
            return str(round((feet * 30.48) + (inches * 2.54), 2))  # Return as string
        elif unit.lower() == "cm":
            return str(round(float(height), 2))
        else:
            raise ValueError("Invalid height unit. Expected 'feet' or 'cm'.")
    except Exception:
        raise ValueError("Invalid height format. Ensure correct input")

def convert_weight_to_kg(weight, unit):
    try:
        if unit.lower() == "lbs":
            return str(round(float(weight) * 0.453592, 2))  # Return as string
        elif unit.lower() == "kg":
            return str(round(float(weight), 2))  # Return as string
        else:
            raise ValueError("Invalid weight unit. Expected 'lbs' or 'kg'.")
    except Exception:
        raise ValueError("Invalid weight format. Ensure correct input (e.g., '150 lbs' or '70').")

def calculate_age(dob):
    dob_date = datetime.strptime(dob, "%d-%m-%Y").date()
    today = date.today()
    return today.year - dob_date.year - ((today.month, today.day) < (dob_date.month, dob_date.day))

def fetch_temperature(lat, lon):
    try:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": WEATHER_API_KEY, 
            "units": "metric"         # Temperature in Celsius
        }
        response = requests.get(WEATHER_API_URL, params=params)
        response.raise_for_status()
        weather_data = response.json()
        return round(weather_data["main"]["temp"], 2)
    except Exception as e:
        print(f"Error fetching temperature: {e}")
        
        return None

def validate_and_extract_data(data):
    user_data = {}
    if "mobile_number" in data: user_data["mobile_number"] = data["mobile_number"]
    if "name" in data: user_data["name"] = data["name"]
    if "goal" in data: user_data["goal"] = data["goal"]
    if "gender" in data: user_data["gender"] = data["gender"]
    if "dob" in data:
        user_data["dob"] = data["dob"]
        user_data["age"] = calculate_age(data["dob"])
    if "height" in data and "height_unit" in data:
        user_data["height"] = {"value": convert_height_to_cm(data["height"], data["height_unit"]), "unit": "cm"}
    if "weight" in data and "weight_unit" in data:
        user_data["weight"] = {"value": convert_weight_to_kg(data["weight"], data["weight_unit"]), "unit": "kg"}
    if "life_routine" in data: user_data["life_routine"] = data["life_routine"]
    if "is_exercise" in data:
        user_data["is_exercise"] = bool(data["is_exercise"])
        if user_data["is_exercise"]:
            user_data["gym_or_yoga"] = data.get("gym_or_yoga", None)
        else:
            user_data["gym_or_yoga"] = None
    if "gym_or_yoga" in data: user_data["gym_or_yoga"] = data["gym_or_yoga"]
    if "intensity" in data: user_data["intensity"] = data["intensity"]
    if "hunger_level" in data: user_data["hunger_level"] = ("Normal" if data["hunger_level"] == "Moderate" else data["hunger_level"])
    if "diet_preference" in data: user_data["diet_preference"] = data["diet_preference"]
    if "allergies" in data: user_data["allergies"] = data["allergies"]
    if "is_personalized" in data and isinstance(data["is_personalized"], bool): user_data["is_personalized"] = data["is_personalized"]
    if "latitude" in data and "longitude" in data:
        temperature = fetch_temperature(data["latitude"], data["longitude"])
        if temperature is not None: user_data["temperature"] = temperature

    return user_data