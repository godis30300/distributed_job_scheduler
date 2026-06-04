from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('jobs/', views.job_list_view, name='job_list'),
    path('jobs/partial/', views.job_list_partial_view, name='job_list_partial'),
    path('jobs/create/', views.job_create_view, name='job_create'),
    path('jobs/<str:job_id>/', views.job_detail_view, name='job_detail'),
    path('jobs/<str:job_id>/edit/', views.job_edit_view, name='job_edit'),
    path('jobs/<str:job_id>/delete/', views.job_delete_view, name='job_delete'),
    path('jobs/<str:job_id>/run/', views.job_run_view, name='job_run'),
    path('runs/', views.job_runs_view, name='job_runs'),
    path('runs/partial/', views.job_runs_partial_view, name='job_runs_partial'),
    path('runs/clear/', views.job_runs_clear_view, name='job_runs_clear'),
    path('runs/<str:run_id>/logs/', views.job_run_logs_view, name='job_run_logs'),
    path('runs/<str:run_id>/retry/', views.job_retry_view, name='job_retry'),
    path('health/', views.health_view, name='health'),
]
