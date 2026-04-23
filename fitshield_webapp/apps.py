from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.dispatch import receiver

class FitshieldWebappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'fitshield_webapp'

    # def ready(self):
    #     from .view.restro.imagetasks import check_and_update_dish_images,update_is_menu_prepared
    #     check_and_update_dish_images(repeat=600) 
    #     update_is_menu_prepared(repeat=60)
    #     import fitshield_webapp.signals  
