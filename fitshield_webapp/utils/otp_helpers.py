import time
import requests
from twilio.rest import Client
from django.core.mail import send_mail
from django.conf import settings
from twilio.base.exceptions import TwilioRestException

def send_otp_via_sms(phone_int, otp, instance_id, access_token):
    
    hisocial_api_url = 'https://hisocial.in/api/send'

    # Prepare payload for the hisocial API
    payload = {
        "number": phone_int,
        "type": "whatsapp",
        "message": f"""Hi, your Fitshield code is {otp}.Use it in 2 minutes or it vanishes like a ninja!""",
        "instance_id": instance_id,
        "access_token": access_token
    }

    try:
        attempts = 0
        success = False
        while attempts < 3 and not success:
            attempts += 1
            response = requests.post(hisocial_api_url, json=payload)
            if response.status_code == 200:
                success = True
            else:
                time.sleep(2)
        
        # Check response status and return success or failure
        if success:
            return True, "OTP sent successfully."
        else:
            try:
                error_details = response.json()
            except ValueError:
                error_details = {"error": "Failed to parse error response."}
            return False, f"Failed to send OTP: {error_details}"
    except Exception as e:
        return False, f"Error occurred while sending OTP: {str(e)}"


def send_otp_via_email(user, email, otp):
    try:
            subject="Your OTP Code",
            message=f"""Hi {user},
            

Your Fitshield OTP code is {otp}.
         

It’s valid for 2 minutes only—tick-tock!
             
This is your key to unlock greatness(or your account). 
            
Got questions? Reach us at : email@fitshield.in
"""
           
            send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email]
            )
            return True, "OTP sent via Email successfully."
    except Exception as e:
        return False, f"Error sending OTP via Email: {str(e)}"


