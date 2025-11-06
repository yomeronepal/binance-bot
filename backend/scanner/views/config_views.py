"""
Configuration monitoring API endpoints.

Provides REST API for monitoring and validating universal configurations.
"""
import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from scanner.config import get_config_manager, detect_market_type, MarketType

logger = logging.getLogger(__name__)


@api_view(['GET'])
def config_summary(request):
    """
    Get summary of all universal configurations.

    GET /api/config/summary

    Returns:
        {
            "total_configs": 2,
            "market_types": ["forex", "binance"],
            "configs": {
                "forex": {...},
                "binance": {...}
            }
        }
    """
    try:
        manager = get_config_manager()
        summary = manager.get_config_summary()

        return Response(summary, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting config summary: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def validate_configs(request):
    """
    Validate all universal configurations.

    GET /api/config/validate

    Returns:
        {
            "all_valid": true,
            "results": {
                "forex": {"is_valid": true, "errors": []},
                "binance": {"is_valid": true, "errors": []}
            }
        }
    """
    try:
        manager = get_config_manager()
        validation_results = manager.validate_all_configs()

        # Format results
        formatted_results = {}
        all_valid = True

        for market_type, (is_valid, errors) in validation_results.items():
            formatted_results[market_type.value] = {
                'is_valid': is_valid,
                'errors': errors
            }
            if not is_valid:
                all_valid = False

        return Response({
            'all_valid': all_valid,
            'results': formatted_results
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error validating configs: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def detect_market(request):
    """
    Detect market type for a given symbol.

    GET /api/config/detect-market?symbol=BTCUSDT

    Query Parameters:
        symbol: Trading pair symbol

    Returns:
        {
            "symbol": "BTCUSDT",
            "market_type": "binance",
            "config_name": "Binance Universal Configuration (OPT6)"
        }
    """
    try:
        symbol = request.query_params.get('symbol')

        if not symbol:
            return Response(
                {'error': 'Symbol parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Detect market type
        market_type = detect_market_type(symbol)

        # Get config
        manager = get_config_manager()
        config = manager.get_config(market_type)

        result = {
            'symbol': symbol,
            'market_type': market_type.value,
        }

        if config:
            result['config_name'] = config.name
            result['config_description'] = config.description
            result['parameters'] = {
                'long_rsi_range': f"{config.long_rsi_min}-{config.long_rsi_max}",
                'short_rsi_range': f"{config.short_rsi_min}-{config.short_rsi_max}",
                'adx_min': config.long_adx_min,
                'sl_atr': config.sl_atr_multiplier,
                'tp_atr': config.tp_atr_multiplier,
                'risk_reward_ratio': f"1:{config.tp_atr_multiplier / config.sl_atr_multiplier:.1f}",
                'min_confidence': config.min_confidence,
                'preferred_timeframes': config.preferred_timeframes
            }

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error detecting market: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def get_config(request, market_type):
    """
    Get detailed configuration for a specific market type.

    GET /api/config/forex
    GET /api/config/binance

    Returns:
        Full configuration details for the specified market type
    """
    try:
        # Parse market type
        try:
            market_enum = MarketType(market_type.lower())
        except ValueError:
            return Response(
                {'error': f'Invalid market type: {market_type}. Must be "forex" or "binance"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get config
        manager = get_config_manager()
        config = manager.get_config(market_enum)

        if not config:
            return Response(
                {'error': f'No configuration found for market type: {market_type}'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(config.to_dict(), status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting config: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def audit_log(request):
    """
    Get configuration audit log.

    GET /api/config/audit-log?limit=100

    Query Parameters:
        limit: Maximum number of entries to return (default: 100)

    Returns:
        List of recent configuration access events
    """
    try:
        limit = int(request.query_params.get('limit', 100))

        manager = get_config_manager()
        log_entries = manager.get_audit_log(limit=limit)

        return Response({
            'count': len(log_entries),
            'entries': log_entries
        }, status=status.HTTP_200_OK)

    except ValueError:
        return Response(
            {'error': 'Invalid limit parameter'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error getting audit log: {e}", exc_info=True)
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint for configuration system.

    GET /api/config/health

    Returns:
        {
            "status": "healthy",
            "configs_loaded": true,
            "all_valid": true
        }
    """
    try:
        manager = get_config_manager()

        # Validate all configs
        validation_results = manager.validate_all_configs()
        all_valid = all(is_valid for is_valid, _ in validation_results.values())

        # Check if configs are loaded
        all_configs = manager.get_all_configs()
        configs_loaded = len(all_configs) >= 2  # Should have Forex and Binance

        is_healthy = all_valid and configs_loaded

        return Response({
            'status': 'healthy' if is_healthy else 'degraded',
            'configs_loaded': configs_loaded,
            'total_configs': len(all_configs),
            'all_valid': all_valid
        }, status=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE)

    except Exception as e:
        logger.error(f"Config health check failed: {e}", exc_info=True)
        return Response({
            'status': 'unhealthy',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
