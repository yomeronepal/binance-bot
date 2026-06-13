"""
User views for authentication and profile management
"""
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.contrib.auth import get_user_model

from users.serializers import RegisterSerializer, UserSerializer, ChangePasswordSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration
    """
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer


class LoginView(TokenObtainPairView):
    """
    API endpoint for user login (JWT token generation)
    """
    permission_classes = (AllowAny,)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Log the user out by blacklisting their refresh token.

    Request body:
        {"refresh": "<refresh_token>"}
    """
    refresh_token = request.data.get('refresh')
    if not refresh_token:
        return Response(
            {"error": "refresh token is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    try:
        RefreshToken(refresh_token).blacklist()
    except TokenError:
        return Response(
            {"error": "Invalid or expired refresh token"},
            status=status.HTTP_400_BAD_REQUEST
        )
    return Response(
        {"message": "Logged out successfully"},
        status=status.HTTP_205_RESET_CONTENT
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Get current user profile
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """
    Update current user profile
    """
    serializer = UserSerializer(request.user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password
    """
    serializer = ChangePasswordSerializer(data=request.data)
    if serializer.is_valid():
        user = request.user
        if not user.check_password(serializer.data.get('old_password')):
            return Response(
                {"old_password": "Wrong password."},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(serializer.data.get('new_password'))
        user.save()
        return Response(
            {"message": "Password updated successfully"},
            status=status.HTTP_200_OK
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
