"""
Signal views - placeholder for future implementation
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_signals(request):
    """
    List trading signals - placeholder
    """
    return Response({
        'message': 'Signals endpoint - to be implemented'
    })
