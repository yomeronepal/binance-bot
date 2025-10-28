"""
API Views - Health check and common endpoints
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint to verify the API is running.
    """
    return Response(
        {
            'status': 'healthy',
            'message': 'Binance Trading Bot API is running'
        },
        status=status.HTTP_200_OK
    )
