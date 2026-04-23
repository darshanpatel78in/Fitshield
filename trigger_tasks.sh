#!/bin/bash

# Navigate to the project directory
cd /home/ubuntu/fitshield || { echo "Failed to change directory"; exit 1; }

# Activate the virtual environment
source env/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }

# Run Python shell commands
python manage.py shell <<EOF
from fitshield_webapp.tasks import *
from fitshield_webapp.view.restro.imagetasks import *
check_unapproved_dishes()
check_and_update_dish_images()
update_is_menu_prepared()
exit()
EOF

# Run process tasks
nohup python manage.py process_tasks --duration=3600 > process_tasks.log
