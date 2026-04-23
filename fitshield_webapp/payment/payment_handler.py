import hashlib
import hmac
import base64
import requests
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
import json
import hashlib
import base64
import requests
import uuid
import logging
import datetime
from django.conf import settings
from django.shortcuts import render, redirect
from django.urls import reverse

PHONEPE_MERCHANT_ID = "M22ST5KMWC5OM"
PHONEPE_MERCHANT_KEY = "a5c47a6c-98ad-4bde-9bfe-5372baa30b4f"
SALT_INDEX = getattr(settings, 'SALT_INDEX', '1')
PHONEPE_BASE_URL = "https://api-preprod.phonepe.com/apis/pg-sandbox/pg/v1/pay"  #bs

logger = logging.getLogger('payment')

def generate_tran_id():
    uuid_part = str(uuid.uuid4()).split('-')[0].upper()  
    now = datetime.datetime.now().strftime('%Y%m%d')
    return f"TRX{now}{uuid_part}"

def generate_checksum(data, salt_key, salt_index):
    checksum_str = data + '/pg/v1/pay' + salt_key
    checksum = hashlib.sha256(checksum_str.encode()).hexdigest() + '###' + salt_index
    return checksum

@csrf_exempt
def initiate_payment(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

    try:
        request_data = json.loads(request.body)
        amount = request_data.get('amount')
        if not amount or not str(amount).isdigit():
            return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)

        callback_url = f"{request.scheme}://{request.get_host()}/payment-callback"
        payload = {
            "merchantId": PHONEPE_MERCHANT_ID,
            "merchantTransactionId": generate_tran_id(),
            "merchantUserId": "USR1231",
            "amount": int(amount) * 100,  # Convert to paisa
            "redirectUrl": callback_url,
            "redirectMode": "POST",
            "callbackUrl": callback_url,
            "mobileNumber": "9512436804",
            "paymentInstrument": {
                "type": "PAY_PAGE"
            }
        }

        data = base64.b64encode(json.dumps(payload).encode()).decode()
        checksum = generate_checksum(data, PHONEPE_MERCHANT_KEY, SALT_INDEX)

        headers = {
            'Content-Type': 'application/json',
            'X-VERIFY': checksum,
        }

        response = requests.post(f"{PHONEPE_BASE_URL}", headers=headers, json={"request": data})
        response_data = response.json()

        logger.info("Initiate payment response: %s", response_data)

        if response_data.get('success'):
            redirect_url = response_data['data']['instrumentResponse']['redirectInfo']['url']
            return JsonResponse({'success': True, 'redirect_url': redirect_url}, status=200)
        else:
            return JsonResponse({'success': False, 'message': response_data.get('message', 'Payment initiation failed')}, status=400)

    except Exception as e:
        logger.error("Error initiating payment: %s", e)
        return JsonResponse({'success': False, 'message': 'An error occurred while initiating payment'}, status=500)

@csrf_exempt
def payment_callback(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)

    try:
        data = json.loads(request.body)
        logger.info("Payment callback data: %s", data)

        if data.get('code') == "PAYMENT_SUCCESS":
            return JsonResponse({'success': True, 'message': 'Payment successful', 'transactionId': data.get('transactionId')}, status=200)
        else:
            return JsonResponse({'success': False, 'message': 'Payment failed', 'details': data}, status=400)

    except Exception as e:
        logger.error("Error handling callback: %s", e)
        return JsonResponse({'success': False, 'message': 'An error occurred while processing the callback'}, status=500)

