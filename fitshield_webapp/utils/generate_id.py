import re
import uuid
import random




def generate_ingredient_id(ingredient_name):
    random_digits = uuid.uuid4()  
    ingredient_id = f"{ingredient_name.replace(' ', '_')}_{random_digits}" 
    return ingredient_id

#resturant related
def generate_restro_id(restroname, pincode):
    prefix = "restro"
    sanitized_restroname = re.sub(r'\W+', '', restroname.replace(" ", ""))  
    sanitized_pincode = re.sub(r'\D', '', str(pincode)) 
    unique_id = uuid.uuid4()

    restro_id = f"{prefix}_{sanitized_restroname}_{sanitized_pincode}_{unique_id}"  
    return restro_id

def generate_query_id(restro_id):
    prefix = "restro"
    last6_digits = restro_id[-6:] 
    unique_id = uuid.uuid4()

    query_id = f"{prefix}_{last6_digits}_query{unique_id}" 
    return query_id

def generate_multiple_query_id():
    unique_id = uuid.uuid4()
    multiple_query_id = f"query_{unique_id}" 
    return multiple_query_id

def generate_review_id(restro_id):
    prefix = "restro"
    last6_digits = restro_id[-6:] 
    unique_id = uuid.uuid4()

    review_id = f"{prefix}_{last6_digits}_review{unique_id}" 
    return review_id

#dish related
def generate_dish_id(restroname,dish_name):
    prefix = "dish"
    sanitized_restroname = re.sub(r'\W+', '', restroname.replace(" ", ""))  
    unique_suffix = str(uuid.uuid4()) 
    sanitized_dish_name = re.sub(r"\s+", "", dish_name.replace("&", "_"))
    dish_id = f"{prefix}_{sanitized_restroname}_{sanitized_dish_name}_{unique_suffix}"
    return dish_id


#user related
def generate_user_id(username):
    prefix = "user"
    sanitized_username = re.sub(r'\W+', '', username.replace(" ", ""))  
    unique_id = uuid.uuid4()

    user_id = f"{prefix}_{sanitized_username}_{unique_id}"
    return user_id

def generate_guest_id(username):
    prefix = "guest"
    sanitized_username = re.sub(r'\W+', '', username.replace(" ", ""))  
    unique_id = uuid.uuid4()
    
    guest_id = f"{prefix}_{sanitized_username}_{unique_id}"
    return guest_id

def generate_user_cart(user_id):
    unique_id = uuid.uuid4()
    prefix = "cart"
    cart_id = f"{prefix}_{user_id}_{unique_id}"
    return cart_id

def generate_session_cart(guest_id):
    unique_id = uuid.uuid4()
    prefix = "cart"
    cart_id = f"{prefix}_{guest_id}_{unique_id}"
    return cart_id

#order cart related
def generate_order_id():
    prefix = "order"
    unique_id = uuid.uuid4()
    order_id = f"{prefix}_{unique_id}"
    return order_id

def generate_host_user_id(user_id):
    unique_id = uuid.uuid4()
    prefix = "host"
    host_user_id = f"{prefix}_{user_id}_{unique_id}"
    return host_user_id

def generate_group_order_id():
    prefix = "group_order"
    unique_id = uuid.uuid4()
    group_order_id = f"{prefix}_{unique_id}"
    return group_order_id

def generate_entry_id(restaurant_name):
    unique_id = uuid.uuid4()
    entry_id = f"contact_{restaurant_name.lower().replace(' ', '')}_{unique_id}"
    return entry_id

