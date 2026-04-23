from django.core.mail import send_mail
import logging
from datetime import datetime

DEFAULT_FROM_EMAIL = "s.fitshield@gmail.com"  # Default sender email
# ADMIN_EMAILS = ["dhartip.fitshield@gmail.com", "poojas.fitshield@gmail.com", "dhruvib.fitshield@gmail.com", "dhruvisha.fitshield@gmail.com", "s.fitshield@gmail.com", "rohant.fitshield@gmail.com"]  # List of recipient emails
ADMIN_EMAILS = ["dhartip.fitshield@gmail.com", "poojas.fitshield@gmail.com", "devasyadave@gmail.com", "jeelb.fitshield@gmail.com", "fitshield.dietfood@gmail.com"]


def send_admin_email(issue_type, restaurant_name=None, restro_id=None, dish_id=None, query=None, description=None, from_email=None, recipients=None):

    sender_email = from_email if from_email else DEFAULT_FROM_EMAIL
    current_time = datetime.utcnow().strftime('%d %b %Y, %I:%M %p')  

    # Set recipients, defaulting to ADMIN_EMAILS if not provided
    recipient_list = recipients if recipients else ADMIN_EMAILS

    # **SUBJECT HANDLING**
    if issue_type == "General Query":
        subject = f"📩 {restaurant_name} Query"
    elif issue_type == "Nutrient Issue":
        subject = f"🚨 Nutrient Calculation Failed in Dish: {dish_id}"
    elif issue_type == "Dish Approve Request":
        subject = f"⏳ Approval Pending for {restaurant_name}"
    elif issue_type == "Restaurant Onboard":
        subject = f"Restaurant Onboard"
    else:
        subject = f"[Update] {restaurant_name if restaurant_name else 'Unknown'} - {restro_id if restro_id else 'No ID'}"

    # **EMAIL BODY GENERATION**
    email_body = f"A NEW {issue_type.upper()} HAS BEEN REPORTED.\n\n"

    if issue_type == "General Query":
        email_body += f"""RESTAURANT DETAILS:
- Name: {restaurant_name}
- ID: {restro_id}
- Submitted At: {current_time}

ISSUE DETAILS:
- Query: {query}
- Description: {description}

ACTION REQUIRED:
Please check and respond to the restaurant.
"""

    elif issue_type == "Nutrient Issue":
        email_body += f"""RESTAURANT DETAILS:
- Name: {restaurant_name}
- Restro ID: {restro_id}
- Dish ID: {dish_id}
- Submitted At: {current_time}

ISSUE DETAILS:
- Issue: Nutrient calculation failed.
- Description: The system was unable to calculate nutrients for Dish ID {dish_id}.

ACTION REQUIRED:
{description}.
"""
    elif issue_type == "Restaurant Onboard":
        email_body += f"""RESTAURANT DETAILS:
- Name: {restaurant_name}
- Restro ID: {restro_id}
- Submitted At: {current_time}

ISSUE DETAILS:
- Issue: New Restaurant has Onboard.
- Description: New Restaurant {restaurant_name} has Onboard .

ACTION REQUIRED:
{description}.
"""
    elif issue_type == "Dish Approve Request":
        email_body += f"""RESTAURANT DETAILS:

- Name: {restaurant_name}
- ID: {restro_id}
- Dish ID: {dish_id}
- Submitted At: {current_time}

ISSUE DETAILS:
- Some dishes have been pending approval for more than 24 hours.

ACTION REQUIRED:
Please review and approve pending dishes in the system.
"""
        
    try:
        send_mail(
            subject=subject,
            message=email_body,
            from_email=sender_email,
            recipient_list=recipient_list, 
            fail_silently=False
        )
        logging.info(f"Email sent from {sender_email} to {', '.join(recipient_list)}: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")

def send_restro_email(issue_type, restaurant_name=None, restro_id=None, restro_email=None, query=None, from_email=None):

    if not restro_email:
        logging.error("No recipient email provided. Email not sent.")
        return

    recipient_list = [restro_email] 
    ADMIN_EMAIL = "partnerfitshield@gmail.com"

    sender_email = ADMIN_EMAIL if ADMIN_EMAIL else DEFAULT_FROM_EMAIL
    email_body = f"A {issue_type.upper()}\n\n"

    if issue_type == "Query Resolved":
        subject = f"Resolved: {query}"
        email_body += f"""
DETAILS:
- Your Query related to {query} has been resolved.
"""
    try:
        send_mail(
            subject=subject,
            message=email_body,
            from_email=sender_email,
            recipient_list=recipient_list, 
            fail_silently=False
        )

        logging.info(f"Email sent from {sender_email} to {', '.join(recipient_list)}: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email: {str(e)}")