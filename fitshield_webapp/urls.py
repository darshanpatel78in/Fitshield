from django.urls import path
from django.shortcuts import render

from fitshield_webapp.view.admin.resturant_support.query_status import update_query_status
from fitshield_webapp.view.restro.edit_dish import update_dish

# Resturant

from .view.restro.authentication_and_registration import get_address, owner_exists, send_otp, restaurant_details, upload_menu, delete_menu
from .view.restro.dishes_management import add_last_reminder_to_dishes, get_dishes, add_dish, get_unverified_dishes,add_ingredients,get_ingredients,generate_pdf

from .view.restro.profile import edit_dish_image, get_restaurant_details, update_restaurant_details
from .view.restro.support_management import support

from .view.restro.table_management import generate_qr,add_floor,add_table,update_floor,remove_floor,remove_table
from .view.restro.order_management import order_history,get_received_orders, table_order_details,update_order_status

from .view.restro.discount_management import get_discount,add_discount
from .view.restro.notification_management import get_notifications

from .view.restro.contact_management import submit_query, get_in_touch
from .view.restro.reviews import get_reviews
from .view.restro.search_query import universal_search
from .view.restro.restructure import update_menu
from .view.restro.nutrition import get_food_suggestions,get_nutrition

# User
from .view.user.user_login import user_data,get_temperature,user_exists,add_user,get_user_data,user_send_otp

from .view.user.cart import add_restaurant_notes,add_to_cart, update_dish_quantity,view_individual_cart,view_group_cart,get_progressbar_data

from .view.user.order_management import create_order, confirm_order
from .view.user.group_order_management import create_group, group_join, group_lock, remove_user_from_group

from .view.user.favourites import add_favourites, get_favourites, get_restaurant, get_homemade_food, get_rawfood
from .view.user.review import submit_review

from .view.user.support_management import  user_support
from .view.user.dishes_management import calc_macros, get_dishes_by_category, get_restaurant_categories, get_restaurant_menu,get_restro_data,get_recommended_dishes
from .view.user.allergy_management import get_allergies,search_allergy,add_allergy

# from .user.payment_management import 
from home_cooking.home_cooking import get_dish
from home_cooking.payment_management import initiate_payment, payment_callback, payment_status

# Admin

from .view.admin.backend_testing.test import status_check
from .view.admin.resturant_support.launch import support_post
from .view.admin.resturant_support.mongosupport import add_is_updated_image_to_all, delete_is_updated_image_from_all, delete_restaurant

urlpatterns = [

    # *******************************Resturant Flow*************************************

    # Authentication and Registration
    path('get-address', get_address, name='get_address'),  
    path('owner-exists', owner_exists, name='owner_exists'),
    path('send-otp', send_otp, name='send_otp'),
    path('restaurant-details', restaurant_details, name='restaurant_details'),
    path('upload-menu', upload_menu, name='upload_menu'),
    path('delete-menu', delete_menu, name='delete_menu'),

     # Dishes Management
    path('dishes', get_dishes, name='get_dishes'),
    path('add-dish', add_dish, name='add_dish'),
    path('update-dish', update_dish, name='update_dish'),
    path('get-unverified-dishes', get_unverified_dishes, name='get_unverified_dishes'),
    
    path('generate-pdf', generate_pdf, name='generate_pdf'),

    # for user side 
    path('user-dish', get_dish, name='user_dish'),
    # Payment Management
    path("initiate-payment", initiate_payment, name="initiate_payment"),
    path("callback", payment_callback, name="payment_callback"),
    path("payment/status/<str:merchant_transaction_id>/", payment_status, name="payment_status"),  


    # Profile
    path('get-restaurant-details', get_restaurant_details, name='get_restaurant_details'),
    path('update-restaurant-details', update_restaurant_details, name='update_restaurant_details'),
    path('edit-dish-image', edit_dish_image, name='edit_dish_image'),

    # Support
    path('support', support, name='support'),

    # Table Management - QR Code
    path('generate-qr', generate_qr, name='generate_qr'),
    path('add-floor',add_floor,name='add_floor'),
    path('add-table',add_table,name='add_table'),
    path('update-floor',update_floor,name='update_floor'),
    path('remove-floor',remove_floor,name='remove_floor'),
    path('remove-table',remove_table,name='remove_table'),
    
    # Orders Management
    path('order-history', order_history, name='order_history'),
    path('get-received-orders',get_received_orders,name='get_received_orders'),
    path('update-order-status',update_order_status,name='update_order_status'),
    path('table-order-details',table_order_details,name='table_order_details'),

    # Discount Management
    path('get-discount', get_discount, name='get_discount'),
    path('add-discount', add_discount, name='add_discount'),

     # Notification Management
    # path('add-notification', add_notification, name='add_notification'),
    path('get-notifications', get_notifications, name='get_notifications'),
  
    # Contact Management
    path('submit-query', submit_query, name='submit_query'),
    path('get-in-touch', get_in_touch, name='get_in_touch'),
    path('update-query-status', update_query_status, name='update_query_status'),

     # Reviews
    path('reviews/<str:restro_id>', get_reviews, name='get_reviews'),

    # Seach Query
    path('universal-search', universal_search, name='universal_search'),

    # ******************************* User-Flow *************************************

    # User Login
    path('user-login', user_data, name='user_data'),
    path('user-send-otp',user_send_otp, name='user_send_otp'),

    #dish management
    path('get-recommended-dishes',get_recommended_dishes,name='get_recommended_dishes'),
    path('get-user-data', get_user_data, name='get_user_data'),
    path('get-restro-data', get_restro_data, name='get_restro_data'),
    path('get-restaurant-menu', get_restaurant_menu, name='get_restaurant_menu'),
    path('calc-macros', calc_macros, name='calc_macros'),
    path('view-individual-cart', view_individual_cart, name='view_individual_cart'),
    path('view-group-cart', view_group_cart, name='view_group_cart'),

    # Cart Management
    path('add-to-cart', add_to_cart, name='add_to_cart'),
    path('update-dish-quantity', update_dish_quantity, name='update_dish_quantity'),
    path('view-individual-cart', view_individual_cart, name='view_individual_cart'),
    path('get-progressbar-data',get_progressbar_data,name='get_progressbar_data'),
    
    # Order Management
    path('create-order', create_order, name='create_order'),
    # path('delete-order', delete_order, name='delete_order'),
    # path('list-order', list_order, name='list_order'),
    # path('update-order', update_order, name='update_order'),
    path('confirm-order', confirm_order, name='confirm_order'),
    
    # Group Order Management
    path('create-group',create_group, name='create_group'),
    path('group-join', group_join, name='group_join'),
    path('group-lock', group_lock, name='group_lock'),
    path('add-restaurant-notes', add_restaurant_notes, name='add_restaurant_notes'),
    path('remove-user-from-group', remove_user_from_group, name='remove_user_from_group'),
    
    #User Support
    path('user-support', user_support, name='user_support'),
    
    #Rawfood,Homemadefood & Favourites
    path('get-rawfood', get_rawfood, name='get_rawfood'),
    path('get-homemade-food', get_homemade_food, name='get_homemade_food'),
    path('add-favourites', add_favourites, name='add_favourites'),
    path('get-favourites', get_favourites, name='get_favourites'),
    path('get-restaurant', get_restaurant, name='get_restaurant'),
    path('submit-review', submit_review, name='submit_review'),


    # ******************************* Admin-Flow *************************************
    
    path('', lambda request: render(request, 'index.html'), name='index'),
    # path('list-logs/<path:relative_path>',list_logs,name='list_logs'),
    path('status', status_check, name='status_check'),
    path('support-post', support_post, name='support_post'),
    # path('upload-video', views.upload_video, name='upload_video'),
    # path('create-thumbnail', views.create_thumbnail, name='create_thumbnail'),
    path('delete-restaurant',delete_restaurant,name='delete_restaurant'),



    #*******************************new***************************
        path('get-temperature', get_temperature, name='get_temperature'),
        # path('scan-restaurant', scan_restaurant, name='scan_restaurant'),
        path('get-restaurant-categories', get_restaurant_categories, name='get_restaurant_categories'),

        path('add-allergy', add_allergy, name='add_allergy'),
        path('get-allergies', get_allergies, name='get_allergies'),

        path('search-allergy', search_allergy, name='search_allergy'),
        path('user-exists', user_exists, name='user_exists'),
        path('add-user', add_user, name='add_user'),
        
        path('add-ingredients', add_ingredients, name='add_ingredients'),
        path('get-ingredients', get_ingredients, name='get_ingredients'),

        path('get-received-orders', get_received_orders, name='get_received_orders'),
        path('get-dishes-by-category', get_dishes_by_category, name='get_dishes_by_category'),
        path('update-menu', update_menu, name='update_menu'),

        path('add-last-reminder-to-dishes', add_last_reminder_to_dishes, name='add_last_reminder_to_dishes'),
        
        path('add-is-updated-image-to-all',add_is_updated_image_to_all,name='add_is_updated_image_to_all'),
        path('delete-is-updated-image-from-all',delete_is_updated_image_from_all,name='delete_is_updated_image_from_all'),
        path('suggestions', get_food_suggestions, name='get_food_suggestions'),
        path('nutrition', get_nutrition, name='get_nutrition'),

]
