from asyncio.log import logger
from django.http import JsonResponse
from django.shortcuts import render
import requests

from config.connection import check_connection
from config.s3_connection import check_s3_connection


def index(request):
    return render(request, 'index.html')  

def find_suitable_http_method(api_url):
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
    mock_data = {"key": "value"} 

    for method in methods:
        try:
            response = None
            if method == "GET":
                response = requests.get(api_url, timeout=5)

            # Log the status and response
            logger.info(f"Testing {method} on {api_url} - Status Code: {response.status_code}")
            logger.info(f"Response: {response.text}")

            # Check for valid methods
            if response.status_code == 200:
                return {"method": method, "status": True, "message": "API is running fine."}
            elif response.status_code == 404:
                return {"method": method, "status": False, "message": "API returned 404: Not Found"}
            elif response.status_code == 405:
                logger.warning(f"{method} method not allowed for {api_url}.")
                continue

        except requests.exceptions.Timeout:
            logger.error(f"Timeout while testing {method} on {api_url}.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error testing {method} on {api_url}: {str(e)}")
            continue

    # If no method works
    return {"method": None, "status": False, "message": "No valid HTTP method found."}


def status_check(request):
    status = {"services": {}, "apis": {}}

    try:
        mongodb_result = check_connection()
        status["services"]["mongodb"] = {
            "status": mongodb_result,
            "message": "MongoDB connection successful." if mongodb_result else "MongoDB connection failed."
        }
    except Exception as e:
        status["services"]["mongodb"] = {
            "status": False,
            "message": f"Error checking MongoDB connection: {str(e)}"
        }

    # AWS S3 Connection Check
    try:
        aws_result = check_s3_connection()
        status["services"]["aws_s3"] = aws_result
    except Exception as e:
        status["services"]["aws_s3"] = {
            "status": False,
            "message": f"Error checking AWS S3 connection: {str(e)}"
        }

    # API URLs Health Check
    # Code - Pooja - add more get api after confirming admin restro
    api_urls = [
        "http://localhost:8000/api/support",
        "http://localhost:8000/api/get-discount?restro_id=restro_SpicyDelight_123456_7e25&is_half=false"
    ]

    for api_url in api_urls:
        try:
            result = find_suitable_http_method(api_url)
            status["apis"][api_url] = result
        except Exception as e:
            logger.error(f"Error while testing API {api_url}: {str(e)}")
            status["apis"][api_url] = {"method": None, "status": False, "message": f"Error checking API: {str(e)}"}

    return JsonResponse(status)