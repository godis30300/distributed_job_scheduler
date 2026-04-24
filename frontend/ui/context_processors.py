from django.conf import settings


def app_settings(request):
    return {
        'DEMO_MODE': settings.DEMO_MODE,
        'BACKEND_API_URL': settings.BACKEND_API_URL,
    }
