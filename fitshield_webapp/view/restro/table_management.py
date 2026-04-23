from datetime import datetime
import json
import logging
from logging.handlers import RotatingFileHandler

from fitshield_webapp.utils.qrcode_manager import generate_qr_code
from ...utils.logging_utils import get_logger
from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from config.connection import db
from django.http import HttpResponse, JsonResponse
from rest_framework.response import Response
import pytz

logger = logging.getLogger(__name__)

restrodata_collection = db["RestroData"]

@csrf_exempt
def generate_qr(request):
    if request.method != "POST":
        logger.warning("Invalid request method: %s. Only POST is allowed.", request.method)
        return JsonResponse({"error": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        logger.info("Received request to generate QR codes. Data: %s", data)
        restro_id = data.get("restro_id")
        floors = data.get("floors", [])

        if not restro_id or not floors:
            logger.warning("Missing required fields: restro_id or floors.")
            return JsonResponse({"error": "Restaurant ID and floors data are required."}, status=400)

        restaurant = restrodata_collection.find_one({"_id": restro_id})
        if not restaurant:
            restaurant = {"_id": restro_id, "floor_detail": []}

        current_time = datetime.utcnow().isoformat()
        updated_floor_detail = {floor['floor_name']: floor for floor in restaurant.get("floor_detail", [])}
        total_tables_count = 0  # Initialize the total table count

        for floor in floors:
            floor_name = floor.get("floor_name")
            new_tables = floor.get("tables", [])

            if not floor_name or not new_tables:
                logger.warning("Incomplete floor data provided: %s", floor)
                return JsonResponse({"error": "Incomplete floor data."}, status=400)

            table_detail = updated_floor_detail.get(floor_name, {"floor_name": floor_name, "tables": []})
            existing_tables = {table['table_number']: table for table in table_detail.get("tables", [])}

            # Generate or update QR codes for each table
            for table_number in new_tables:
                logger.debug("Processing QR code for table_number: %s on floor: %s", table_number, floor_name)
                if str(table_number) in existing_tables:
                    qr_url = generate_qr_code(restro_id, table_number, floor_name)
                    existing_tables[str(table_number)]['qr_code_url'] = qr_url
                    existing_tables[str(table_number)]['updated_at'] = current_time
                    logger.info("Updated QR code URL for existing table: %s", qr_url)
                else:
                    qr_url = generate_qr_code(restro_id, table_number, floor_name)
                    logger.info("Generated new QR code URL: %s", qr_url)
                    existing_tables[str(table_number)] = {
                        "table_number": str(table_number),
                        "qr_code_url": qr_url,
                        "created_at": current_time,
                        "updated_at": current_time
                    }

            # Update table count and table details
            table_detail['tables'] = list(existing_tables.values())
            table_detail['number_of_tables'] = len(existing_tables)
            total_tables_count += table_detail['number_of_tables']
            updated_floor_detail[floor_name] = table_detail

        # Save updated floor details back to the database
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": {
                "floor_detail": list(updated_floor_detail.values()),
                "updated_at": datetime.utcnow().isoformat()
            }},
            upsert=True
        )
        logger.info("QR codes generated and table details updated successfully for restro_id: %s", restro_id)
        return JsonResponse({
            "message": "QR codes generated and table details updated successfully.",
            "floor_detail": list(updated_floor_detail.values()),
            "number_of_tables": total_tables_count  # Return the total count of tables across all floors
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload in the request.")
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    except Exception as e:
        logger.error("An error occurred: %s", str(e))
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def add_floor(request):
    """
    API to add a new floor (without any tables) to a restaurant.

    Expected JSON payload:
    {
        "restro_id": "restro_id",
        "floor_name": "new floor name"
    }
    """
    if request.method != "POST":
        logger.warning("Invalid request method: %s. Only POST is allowed.", request.method)
        return JsonResponse({"error": "Invalid request method. Use POST."}, status=405)

    try:
        data = json.loads(request.body)
        logger.info("Received add floor request: %s", data)
        
        restro_id = data.get("restro_id")
        floor_name = data.get("floor_name")
        
        if not restro_id or not floor_name:
            logger.warning("Missing required fields: restro_id or floor_name.")
            return JsonResponse({"error": "restro_id and floor_name are required."}, status=400)
        
        # Normalize the provided floor name for comparison.
        normalized_new_floor = floor_name.replace(" ", "").lower()
        current_time = datetime.utcnow().isoformat()

        # Fetch the restaurant document.
        restaurant = restrodata_collection.find_one({"_id": restro_id})
        if restaurant:
            floor_details = restaurant.get("floor_detail", [])
            # Check if a floor with the same normalized name already exists.
            for floor in floor_details:
                stored_floor_name = floor.get("floor_name", "")
                normalized_stored = stored_floor_name.replace(" ", "").lower()
                if normalized_stored == normalized_new_floor:
                    logger.warning("Floor '%s' already exists for restaurant: %s", floor_name, restro_id)
                    return JsonResponse({"error": f"Floor '{floor_name}' already exists."}, status=400)
        else:
            # Initialize the restaurant document if not found.
            restaurant = {"_id": restro_id, "floor_detail": []}
            floor_details = restaurant["floor_detail"]
        
        # Create a new floor object with no tables.
        new_floor = {
            "floor_name": floor_name,
            "tables": [],
            "number_of_tables": 0,
            "created_at": current_time,
            "updated_at": current_time
        }
        
        # Append the new floor to the floor details.
        floor_details.append(new_floor)
        
        # Update (or insert) the restaurant document in the database.
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": {
                "floor_detail": floor_details,
                "updated_at": current_time
            }},
            upsert=True
        )
        
        logger.info("New floor '%s' added successfully for restaurant: %s", floor_name, restro_id)
        return JsonResponse({
            "message": f"Floor '{floor_name}' added successfully.",
            "floor_detail": new_floor
        })
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload in the request.")
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error("An error occurred while adding floor: %s", str(e))
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def add_table(request):
    """
    API to add a new table to an existing floor of a restaurant.

    Expected JSON payload:
    {
        "restro_id": "id",
        "floor_name": "1st floor",
        "tables": {
            "table_number": "2"  // it cannot be null or empty
        }
    }
    """
    if request.method != "POST":
        logger.warning("Invalid request method: %s. Only POST is allowed.", request.method)
        return JsonResponse({"error": "Invalid request method."}, status=405)

    try:
        data = json.loads(request.body)
        logger.info("Received add table request: %s", data)

        restro_id = data.get("restro_id")
        floor_name = data.get("floor_name")
        table_data = data.get("table")

        if not restro_id or not floor_name or not table_data:
            logger.warning("Missing required fields: restro_id, floor_name, or tables.")
            return JsonResponse({"error": "restro_id, floor_name, and tables are required."}, status=400)

        table_number = table_data.get("table_number")
        if table_number is None or str(table_number).strip() == "":
            logger.warning("Invalid table_number provided: %s", table_number)
            return JsonResponse({"error": "table_number cannot be null or empty."}, status=400)

        table_number_str = str(table_number).strip()
        current_time = datetime.utcnow().isoformat()

        # Fetch the restaurant document from the database.
        restaurant = restrodata_collection.find_one({"_id": restro_id})
        if not restaurant:
            logger.warning("Restaurant not found for restro_id: %s", restro_id)
            return JsonResponse({"error": "Restaurant not found."}, status=404)

        # Check if the specified floor exists.
        floor_details = restaurant.get("floor_detail", [])
        floor_obj = None
        for floor in floor_details:
            if floor.get("floor_name") == floor_name:
                floor_obj = floor
                break

        if not floor_obj:
            logger.warning("Floor '%s' not found for restaurant: %s", floor_name, restro_id)
            return JsonResponse({"error": f"Floor '{floor_name}' not found."}, status=404)

        # Check if the table already exists on this floor.
        existing_tables = floor_obj.get("tables", [])
        for table in existing_tables:
            if table.get("table_number") == table_number_str:
                logger.warning("Table %s already exists on floor '%s' for restaurant: %s",
                               table_number_str, floor_name, restro_id)
                return JsonResponse({"error": f"Table {table_number_str} already exists on floor '{floor_name}'."},
                                    status=400)

        # Generate the QR code URL using the generate_qr_code function.
        qr_url = generate_qr_code(restro_id, table_number_str, floor_name)
        logger.info("Generated QR code for table %s on floor %s: %s",
                    table_number_str, floor_name, qr_url)

        # Create the new table object.
        new_table = {
            "table_number": table_number_str,
            "qr_code_url": qr_url,
            "created_at": current_time,
            "updated_at": current_time
        }

        # Append the new table and update the table count.
        existing_tables.append(new_table)
        floor_obj["tables"] = existing_tables
        floor_obj["number_of_tables"] = len(existing_tables)

        # Update the restaurant document with the modified floor details.
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": {
                "floor_detail": floor_details,
                "updated_at": current_time
            }}
        )

        logger.info("Table %s added successfully on floor '%s' for restaurant: %s",
                    table_number_str, floor_name, restro_id)
        return JsonResponse({
            "message": f"Table {table_number_str} added successfully on floor '{floor_name}'.",
            "table_detail": new_table
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload.")
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error("An error occurred while adding table: %s", str(e))
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def update_floor(request):
    """
    API to update an existing floor's name for a restaurant via the PUT method.
    
    Expected JSON payload:
    {
      "restro_id": "restaurant id",
      "floor_name": "existing floor name",   // used to locate the floor
      "new_floor_name": "new floor name"       // required; new name for the floor
    }
    
    Behavior:
      - The floor is identified using "floor_name".
      - If "new_floor_name" is provided, update the floor's name.
      - Ensure the new floor name does not already exist in the restaurant.
    """
    if request.method != "PUT":
        logger.warning("Invalid request method: %s. Only PUT is allowed.", request.method)
        return JsonResponse({"error": "Invalid request method. Use PUT."}, status=405)

    try:
        data = json.loads(request.body)
        logger.info("Received update floor request: %s", data)

        restro_id = data.get("restro_id")
        current_floor_name = data.get("floor_name")  # current name used to identify the floor
        new_floor_name = data.get("new_floor_name")    # required new name for the floor

        if not restro_id or not current_floor_name or not new_floor_name:
            logger.warning("Missing required fields: restro_id, floor_name, or new_floor_name.")
            return JsonResponse({"error": "restro_id, floor_name, and new_floor_name are required."}, status=400)

        current_time = datetime.utcnow().isoformat()

        # Fetch the restaurant document.
        restaurant = restrodata_collection.find_one({"_id": restro_id})
        if not restaurant:
            logger.warning("Restaurant not found for restro_id: %s", restro_id)
            return JsonResponse({"error": "Restaurant not found."}, status=404)

        floor_details = restaurant.get("floor_detail", [])
        floor_obj = None

        # Identify the floor using the current floor name.
        for floor in floor_details:
            if floor.get("floor_name") == current_floor_name:
                floor_obj = floor
                break

        if not floor_obj:
            logger.warning("Floor '%s' not found for restaurant: %s", current_floor_name, restro_id)
            return JsonResponse({"error": f"Floor '{current_floor_name}' not found."}, status=404)

        # Check if the new floor name already exists in the database (normalized comparison).
        normalized_new_floor = new_floor_name.replace(" ", "").lower()
        for floor in floor_details:
            stored_floor_name = floor.get("floor_name", "")
            normalized_stored = stored_floor_name.replace(" ", "").lower()
            if normalized_stored == normalized_new_floor:
                logger.warning("Floor '%s' already exists for restaurant: %s", new_floor_name, restro_id)
                return JsonResponse({"error": f"Floor '{new_floor_name}' already exists."}, status=400)

        # If the new floor name is valid, update the floor name.
        floor_obj["floor_name"] = new_floor_name

        # Update the restaurant document in the database.
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": {
                "floor_detail": floor_details,
                "updated_at": current_time
            }}
        )

        logger.info("Floor '%s' updated to '%s' successfully for restaurant: %s", current_floor_name, new_floor_name, restro_id)
        return JsonResponse({
            "message": f"Floor '{current_floor_name}' updated to '{new_floor_name}' successfully.",
            "floor_detail": floor_obj
        })

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload.")
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error("An error occurred while updating floor: %s", str(e))
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def remove_floor(request):
    """
    API to remove a floor from a restaurant.
    
    Expected JSON payload:
    {
        "restro_id": "id",
        "floor_name": "1st"
    }
    """
    if request.method != "DELETE":
        logger.warning("Invalid request method: %s. Only DELETE is allowed.", request.method)
        return JsonResponse({"error": "Invalid request method. Use DELETE."}, status=405)

    try:
        data = json.loads(request.body)
        restro_id = data.get("restro_id")
        floor_name = data.get("floor_name")

        if not restro_id or not floor_name:
            logger.warning("Missing required fields: restro_id or floor_name.")
            return JsonResponse({"error": "restro_id and floor_name are required."}, status=400)

        # Fetch the restaurant document.
        restaurant = restrodata_collection.find_one({"_id": restro_id})
        if not restaurant:
            logger.warning("Restaurant not found for restro_id: %s", restro_id)
            return JsonResponse({"error": "Restaurant not found."}, status=404)

        floor_details = restaurant.get("floor_detail", [])
        
        # Check if the floor exists.
        floor_exists = any(floor.get("floor_name") == floor_name for floor in floor_details)
        if not floor_exists:
            logger.warning("Floor '%s' not found for restaurant: %s", floor_name, restro_id)
            return JsonResponse({"error": f"Floor '{floor_name}' not found."}, status=404)

        # Remove the floor from the list.
        updated_floor_details = [floor for floor in floor_details if floor.get("floor_name") != floor_name]

        current_time = datetime.utcnow().isoformat()
        # Update the restaurant document in the database.
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": {
                "floor_detail": updated_floor_details,
                "updated_at": current_time
            }}
        )
        logger.info("Floor '%s' removed successfully for restaurant: %s", floor_name, restro_id)
        return JsonResponse({"message": f"Floor '{floor_name}' removed successfully."})

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload.")
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error("An error occurred while removing floor: %s", str(e))
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def remove_table(request):
    """
    API to remove a table from a specific floor in a restaurant.
    
    Expected JSON payload:
    {
        "restro_id": "id",
        "floor_name": "1st floor",
        "table_number": "2"
    }
    """
    if request.method != "DELETE":
        logger.warning("Invalid request method: %s. Only DELETE is allowed.", request.method)
        return JsonResponse({"error": "Invalid request method. Use DELETE."}, status=405)

    try:
        data = json.loads(request.body)
        restro_id = data.get("restro_id")
        floor_name = data.get("floor_name")
        table_number = data.get("table_number")

        if not restro_id or not floor_name or not table_number:
            logger.warning("Missing required fields: restro_id, floor_name, or table_number.")
            return JsonResponse({"error": "restro_id, floor_name, and table_number are required."}, status=400)

        # Fetch the restaurant document.
        restaurant = restrodata_collection.find_one({"_id": restro_id})
        if not restaurant:
            logger.warning("Restaurant not found for restro_id: %s", restro_id)
            return JsonResponse({"error": "Restaurant not found."}, status=404)

        floor_details = restaurant.get("floor_detail", [])
        floor_obj = None

        # Locate the floor by floor_name.
        for floor in floor_details:
            if floor.get("floor_name") == floor_name:
                floor_obj = floor
                break

        if not floor_obj:
            logger.warning("Floor '%s' not found for restaurant: %s", floor_name, restro_id)
            return JsonResponse({"error": f"Floor '{floor_name}' not found."}, status=404)

        # Check if the table exists on the specified floor.
        existing_tables = floor_obj.get("tables", [])
        table_exists = any(table.get("table_number") == table_number for table in existing_tables)
        if not table_exists:
            logger.warning("Table '%s' not found on floor '%s' for restaurant: %s", table_number, floor_name, restro_id)
            return JsonResponse({"error": f"Table '{table_number}' not found on floor '{floor_name}'."}, status=404)

        # Remove the table from the floor's table list.
        updated_tables = [table for table in existing_tables if table.get("table_number") != table_number]
        floor_obj["tables"] = updated_tables
        floor_obj["number_of_tables"] = len(updated_tables)

        # Update the restaurant document in the database.
        current_time = datetime.utcnow().isoformat()
        restrodata_collection.update_one(
            {"_id": restro_id},
            {"$set": {
                "floor_detail": floor_details,
                "updated_at": current_time
            }}
        )

        logger.info("Table '%s' removed successfully from floor '%s' for restaurant: %s", table_number, floor_name, restro_id)
        return JsonResponse({"message": f"Table '{table_number}' removed successfully from floor '{floor_name}'."})

    except json.JSONDecodeError:
        logger.error("Invalid JSON payload.")
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.error("An error occurred while removing table: %s", str(e))
        return JsonResponse({"error": str(e)}, status=500)


