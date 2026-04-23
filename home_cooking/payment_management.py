import base64
import hashlib
import json
import logging
import requests
import time
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from config.connection import db

logger = logging.getLogger(__name__)


@csrf_exempt
def initiate_payment(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        # Parse request body
        try:
            request_body = json.loads(request.body)
            amount = request_body.get("amount")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        # Validate amount
        if not amount:
            return JsonResponse({"error": "Amount is required"}, status=400)

        try:
            amount = int(float(amount))
            if amount <= 0:
                return JsonResponse({"error": "Invalid amount"}, status=400)
        except ValueError:
            return JsonResponse({"error": "Invalid amount format"}, status=400)

        merchant_transaction_id = request_body['transaction_id']

        payload = {
            "merchantId": settings.PHONEPE_MERCHANT_ID,
            "merchantTransactionId": merchant_transaction_id,
            "amount": amount,
            "callbackUrl": settings.PHONEPE_CALLBACK_URL,
            "redirectUrl": request_body['redirect_url'],
            "paymentInstrument": {"type": "PAY_PAGE"},
        }

        payload_str = json.dumps(payload)
        encoded_payload = base64.b64encode(payload_str.encode()).decode()
        checksum = (
                hashlib.sha256(
                    f"{encoded_payload}/pg/v1/pay{settings.PHONEPE_SALT_KEY}".encode()
                ).hexdigest()
                + f"###{settings.PHONEPE_SALT_INDEX}"
        )

        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
        }

        response = requests.post(
            settings.PHONEPE_API_URL + "/pg/v1/pay",
            json={"request": encoded_payload},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            db["Payments"].insert_one(
                {
                    "transaction_id": merchant_transaction_id,
                    "amount": amount,
                    "cart_id": request_body["cart_id"],
                    "redirect_url": request_body["redirect_url"],
                    "timestamp": request_body["timestamp"],
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )
            qr_data = data["data"]["instrumentResponse"]["redirectInfo"]["url"]
            logger.info(
                f"Payment QR generated for transaction: {merchant_transaction_id}"
            )
            return JsonResponse(
                {"qr_data": qr_data, "transaction_id": merchant_transaction_id}
            )

        logger.error(f"QR generation failed: {data.get('message', 'Unknown error')}")
        return JsonResponse(
            {"error": data.get("message", "QR generation failed")}, status=400
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"PhonePe API error: {str(e)}")
        return JsonResponse({"error": "Payment service unavailable"}, status=503)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
def payment_callback(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:

        initial_data = json.loads(request.body)
        if not initial_data.get("response"):
            logger.error(f"Missing response field. Received: {initial_data}")
            return JsonResponse({"error": "Missing response field"}, status=400)

        # Decode the base64 response
        try:
            decoded_data = base64.b64decode(initial_data["response"])
            response = json.loads(decoded_data)
        except Exception as e:
            logger.error(f"Failed to decode response: {str(e)}")
            return JsonResponse({"error": "Invalid response format"}, status=400)

        if not response.get("data") or not response.get("code"):
            logger.error(f"Invalid response format. Received: {response}")
            return JsonResponse({"error": "Invalid response format"}, status=400)

        merchant_transaction_id = response["data"]["merchantTransactionId"]
        transaction_id = response["data"]["transactionId"]

        status_url = f"{settings.PHONEPE_API_URL}/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{merchant_transaction_id}"
        checksum = (
                hashlib.sha256(
                    f"/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{merchant_transaction_id}{settings.PHONEPE_SALT_KEY}".encode()
                ).hexdigest()
                + "###"
                + settings.PHONEPE_SALT_INDEX
        )

        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": settings.PHONEPE_MERCHANT_ID,
        }

        status_response = requests.get(status_url, headers=headers)
        status_data = status_response.json()
        print("Status API Response:", status_data)

        db["Payments"].update_one(
            {
                "transaction_id": merchant_transaction_id,
            },
            {
                "$set": {
                    "status": response["code"],
                    "callback_meta": response,
                    "updated_at": int(time.time()),
                }
            },
        )

        if response["success"] and response["code"] == "PAYMENT_SUCCESS":
            return JsonResponse(
                {"message": f"Payment Successful! Transaction ID: {transaction_id}"}
            )
        else:
            return JsonResponse(
                {
                    "message": f"Payment Failed or Pending: {response.get('message', 'Unknown error')}"
                }
            )

    except json.JSONDecodeError:
        logger.error("Invalid JSON in callback request")
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Callback processing error: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)


@csrf_exempt
def payment_status(request, merchant_transaction_id):
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        if not merchant_transaction_id:
            return JsonResponse({"error": "Transaction ID is required"}, status=400)

        # Generate checksum directly for status API
        base_string = f"/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{merchant_transaction_id}{settings.PHONEPE_SALT_KEY}"
        checksum = hashlib.sha256(base_string.encode()).hexdigest() + "###" + settings.PHONEPE_SALT_INDEX

        headers = {
            "Content-Type": "application/json",
            "X-VERIFY": checksum,
            "X-MERCHANT-ID": settings.PHONEPE_MERCHANT_ID,
        }

        status_url = f"{settings.PHONEPE_API_URL}/pg/v1/status/{settings.PHONEPE_MERCHANT_ID}/{merchant_transaction_id}"
        
        response = requests.get(
            status_url,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            payment_info = data.get("data", {})
            return JsonResponse(
                {
                    "status": payment_info.get("state", "UNKNOWN"),
                    "amount": payment_info.get("amount", 0),
                    "transaction_id": merchant_transaction_id,
                }
            )

        logger.error(f"Status check failed: {data.get('message', 'Unknown error')}")
        return JsonResponse(
            {"error": data.get("message", "Status check failed")}, status=400
        )

    except requests.exceptions.RequestException as e:
        logger.error(f"PhonePe API error: {str(e)}")
        return JsonResponse({"error": "Payment service unavailable"}, status=503)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({"error": "Internal server error"}, status=500)