"""
API views for chart annotations (Fib levels, support/resistance)
"""
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal

from .models_chart import ChartAnnotation, FibonacciSetup

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def chart_annotations(request, symbol=None):
    """
    GET: List all annotations for a symbol
    POST: Create new annotation
    """
    if request.method == 'GET':
        if not symbol:
            return Response({'error': 'Symbol required'}, status=400)
        
        symbol = symbol.upper()
        annotations = ChartAnnotation.objects.filter(symbol=symbol, is_active=True)
        
        return Response({
            'symbol': symbol,
            'annotations': [
                {
                    'id': a.id,
                    'type': a.annotation_type,
                    'price_level': float(a.price_level),
                    'label': a.label,
                    'color': a.color,
                    'notes': a.notes,
                }
                for a in annotations
            ]
        })
    
    elif request.method == 'POST':
        try:
            data = request.data
            annotation = ChartAnnotation.objects.create(
                symbol=data['symbol'].upper(),
                annotation_type=data.get('type', 'FIB'),
                price_level=Decimal(str(data['price_level'])),
                label=data.get('label', ''),
                color=data.get('color', '#3b82f6'),
                notes=data.get('notes', ''),
            )
            return Response({
                'id': annotation.id,
                'message': 'Annotation created'
            }, status=201)
        except Exception as e:
            return Response({'error': str(e)}, status=400)


@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_annotation(request, annotation_id):
    """Delete an annotation."""
    try:
        annotation = ChartAnnotation.objects.get(id=annotation_id)
        annotation.delete()
        return Response({'message': 'Deleted'})
    except ChartAnnotation.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([AllowAny])
def fibonacci_setup(request, symbol=None):
    """
    GET: Get Fib setup for symbol with calculated levels
    POST: Create/update Fib setup
    DELETE: Remove Fib setup
    """
    if not symbol:
        return Response({'error': 'Symbol required'}, status=400)
    
    symbol = symbol.upper()
    
    if request.method == 'GET':
        try:
            setup = FibonacciSetup.objects.get(symbol=symbol)
            levels = setup.get_fib_levels()
            return Response({
                'symbol': symbol,
                'swing_high': float(setup.swing_high),
                'swing_low': float(setup.swing_low),
                'direction': setup.direction,
                'notes': setup.notes,
                'levels': {k: round(v, 8) for k, v in levels.items()},
                'updated_at': setup.updated_at.isoformat(),
            })
        except FibonacciSetup.DoesNotExist:
            return Response({'symbol': symbol, 'exists': False})
    
    elif request.method == 'POST':
        try:
            data = request.data
            setup, created = FibonacciSetup.objects.update_or_create(
                symbol=symbol,
                defaults={
                    'swing_high': Decimal(str(data['swing_high'])),
                    'swing_low': Decimal(str(data['swing_low'])),
                    'direction': data.get('direction', 'UP'),
                    'notes': data.get('notes', ''),
                }
            )
            levels = setup.get_fib_levels()
            return Response({
                'symbol': symbol,
                'swing_high': float(setup.swing_high),
                'swing_low': float(setup.swing_low),
                'direction': setup.direction,
                'levels': {k: round(v, 8) for k, v in levels.items()},
                'created': created,
            }, status=201 if created else 200)
        except Exception as e:
            return Response({'error': str(e)}, status=400)
    
    elif request.method == 'DELETE':
        try:
            FibonacciSetup.objects.filter(symbol=symbol).delete()
            return Response({'message': 'Deleted'})
        except Exception as e:
            return Response({'error': str(e)}, status=400)
