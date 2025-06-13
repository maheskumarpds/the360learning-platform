"""
ASGI config for learning_is_easy project.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learning_is_easy.settings')

application = get_asgi_application()
