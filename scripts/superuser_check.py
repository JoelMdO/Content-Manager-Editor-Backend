## Steps to check if the superuser exists in the Django application:
# 1. Ensure that the Django environment is set up correctly and that you have access to the Django shell.
# 2. Run the following code in the Django shell to check for superusers:
# python@c6b17816e31b:/app/src$ python

from django.contrib.auth.models import User
superusers = User.objects.filter(is_superuser=True)
for user in superusers:
    print(f"Username: {user.username}, Email: {user.email}") #type: ignore

# Python 3.14.3 (main, Feb 24 2026, 19:48:53) [GCC 14.2.0] on linux
# Type "help", "copyright", "credits" or "license" for more information.
# >>> from django.contrib.auth.models import User
# ... superusers = User.objects.filter(is_superuser=True)
# ... for user in superusers:
# ...     print(f"Username: {user.username}, Email: {user.email}")

# exit 
exit()