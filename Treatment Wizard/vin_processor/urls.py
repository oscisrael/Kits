from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('start/', views.start_processing, name='start_processing'),
    path('progress/<int:task_id>/', views.progress_status, name='progress_status'),
    path('results/<int:task_id>/', views.results, name='results'),
]
