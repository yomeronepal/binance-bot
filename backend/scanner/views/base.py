"""
Scanner views - placeholder for future implementation
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def scanner_status(request):
    """
    Scanner status endpoint - placeholder
    """
    return Response({
        'message': 'Scanner endpoint - to be implemented'
    })
