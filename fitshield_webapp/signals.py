# from django.db.models.signals import post_migrate
# from django.dispatch import receiver
# from background_task.models import Task
# # from fitshield_webapp.tasks import check_unapproved_dishes

# @receiver(post_migrate)
# def schedule_background_tasks(sender, **kwargs):
#     if not Task.objects.filter(task_name="fitshield_webapp.tasks.check_unapproved_dishes").exists():
#         check_unapproved_dishes(repeat=7200)  # Runs every 2 hours
