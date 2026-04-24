from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect

urlpatterns = [
    path('', lambda request: redirect('dashboard'), name='root'),
    path('admin/', admin.site.urls),
    path('', include('ui.urls')),
]
