import logging
from datetime import datetime, timedelta, timezone
from django.utils.timezone import now, make_aware, is_naive
from django.core.mail import send_mail
from config.connection import db
from fitshield import settings
from background_task import background

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Get unapproved dishses - dish not approved yet + dish which created 12 hrs ago + no mail sent in last 2 hrs
def get_unapproved_dishes():
    try:
        dish_collection = db["RestaurantMenuData"]
        twelve_hours_ago = (now() - timedelta(hours=12)).replace(tzinfo=None).isoformat(timespec='microseconds')
        two_hours_ago = (now() - timedelta(hours=2)).replace(tzinfo=None).isoformat(timespec='microseconds')

        unapproved_dishes = list(dish_collection.aggregate([
            {"$unwind": "$menu"},
            {"$match": {
                "menu.is_dish_approved": False,
                "menu.created_at": {"$lte": twelve_hours_ago},
                "menu.last_reminder_sent": {"$lte": two_hours_ago}
            }},
            {"$group": {
                "_id": "$_id",
                "dishes": {"$push": {
                    "_id": "$menu._id",
                    "dish_name": "$menu.dish_name"
                }}
            }}
        ]))
        return unapproved_dishes, two_hours_ago

    except Exception as e:
        logger.error(f"Error in get_unapproved_dishes: {str(e)}")
        return [], None


def get_restro_name_from_id(unapproved_dishes):
    restro_collection = db["RestroData"]
    restaurant_data = []

    for restaurant in unapproved_dishes:
        restro_id = restaurant["_id"]
        logger.info(f"Processing dishes for restaurant ID: {restro_id}")

        restaurant_info = restro_collection.find_one({"_id": restro_id})

        if not restaurant_info:
            logger.warning(f"Restaurant with ID {restro_id} not found.")
            restaurant_name = "Unknown Restaurant"
        else:
            restaurant_name = restaurant_info.get("name", "Unknown Restaurant")

        dishes = restaurant["dishes"]
        restaurant_data.append((restaurant_name, dishes, restro_id))

    return restaurant_data

#  The dish has never had a reminder sent + mail was sent more than two hours ago
def get_dishes_needing_reminder(dishes, two_hours_ago):
    dishes_needing_reminder = [
        dish for dish in dishes
        if not dish.get("last_reminder_sent") or (
            dish.get("last_reminder_sent") and
            isinstance(dish["last_reminder_sent"], str) and
            datetime.fromisoformat(dish["last_reminder_sent"]) <= two_hours_ago
        )
    ]
    return dishes_needing_reminder

# In this format mail will get send
def prepare_format_mail(dishes_needing_reminder):
    dish_details = "\n".join([f"- {dish['dish_name']} - ID: {dish['_id']}" for dish in dishes_needing_reminder])
    return dish_details

def pass_mail(restaurant_name, dish_details, restro_id, dishes_needing_reminder):
    if not dishes_needing_reminder:
        return f"No unapproved dishes needing reminder for {restaurant_name} ({restro_id}). Skipping"
    
    dish_collection = db["RestaurantMenuData"]

    email_body = f"""
        The following dishes in your menu have been unapproved for over 12 hours:

        {dish_details}

        Please review and approve them in your dashboard.
        """

    send_mail(
        subject=f"Approval Needed for {restaurant_name}",
        message=email_body,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=["dhartip.fitshield@gmail.com"],
        fail_silently=False,
    )

    logger.info(f"Sent email for {restaurant_name} ({restro_id})")

    for dish in dishes_needing_reminder:
        last_reminder_sent = datetime.now(timezone.utc)
        last_reminder_sent_naive = last_reminder_sent.replace(tzinfo=None)
        formatted_time = last_reminder_sent_naive.isoformat()
        print(f"check format before saving to db:{formatted_time}")

        update_result = dish_collection.update_one(
            {"_id": restro_id, "menu._id": dish["_id"]},
            {"$set": {"menu.$.last_reminder_sent": formatted_time}}
        )

        logger.info(f"Updated last_reminder_sent for dish ID: {dish['_id']}")

    logger.info("Task Completed: Unapproved dish reminders sent where necessary.")

@background(schedule=60)
def check_unapproved_dishes():
    logger.info("Checking unapproved dishes...")
    unapproved_dishes, two_hours_ago = get_unapproved_dishes()
    print(f"unapproved_dishes: {unapproved_dishes}")

    if not unapproved_dishes:
        logger.info("No unapproved dishes found.")  
        return

    restaurant_data = get_restro_name_from_id(unapproved_dishes)

    for restaurant_name, dishes, restro_id in restaurant_data:
        dishes_needing_reminder = get_dishes_needing_reminder(dishes, two_hours_ago)
        print(f"dishes_needing_reminder: {dishes_needing_reminder}")

        dish_details = prepare_format_mail(dishes_needing_reminder)
        pass_mail(restaurant_name, dish_details, restro_id, dishes_needing_reminder)

