"""
WSGI config for learning_is_easy project.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learning_is_easy.settings')

application = get_wsgi_application()
