"""
User URL Configuration
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Profile endpoints
    path('profile/', views.get_user_profile, name='profile'),
    path('profile/update/', views.update_user_profile, name='profile-update'),
    path('change-password/', views.change_password, name='change-password'),
]
