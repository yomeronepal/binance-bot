"""
API Views - Health check and common endpoints
"""
from datetime import datetime, timezone, timedelta
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


NEPAL_TZ_OFFSET = timedelta(hours=5, minutes=45)
US_EST_OFFSET = timedelta(hours=-5)

TRADING_WINDOWS = [
    (17, 0, 18, 0),
    (21, 0, 23, 0),
]


def get_timezone_times():
    """Get current time in multiple timezones."""
    utc_now = datetime.now(timezone.utc)
    nepal_now = utc_now + NEPAL_TZ_OFFSET

    jan = datetime(utc_now.year, 1, 1, tzinfo=timezone.utc)
    jul = datetime(utc_now.year, 7, 1, tzinfo=timezone.utc)
    is_dst = utc_now.month >= 3 and utc_now.month <= 11

    us_offset = US_EST_OFFSET + timedelta(hours=1) if is_dst else US_EST_OFFSET
    us_now = utc_now + us_offset

    return utc_now, nepal_now, us_now, is_dst


def is_within_trading_window():
    """Check if current Nepal time is within trading windows."""
    _, nepal_now, _, _ = get_timezone_times()
    current_time_minutes = nepal_now.hour * 60 + nepal_now.minute

    for start_hour, start_min, end_hour, end_min in TRADING_WINDOWS:
        window_start = start_hour * 60 + start_min
        window_end = end_hour * 60 + end_min
        if window_start <= current_time_minutes < window_end:
            return True
    return False


def get_next_window():
    """Get the next trading window start time."""
    _, nepal_now, _, _ = get_timezone_times()
    current_time_minutes = nepal_now.hour * 60 + nepal_now.minute

    if current_time_minutes < 17 * 60:
        return "17:00 NPT"
    elif current_time_minutes >= 18 * 60 and current_time_minutes < 21 * 60:
        return "21:00 NPT"
    else:
        return "17:00 NPT (tomorrow)"


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint to verify the API is running."""
    return Response(
        {
            'status': 'healthy',
            'message': 'Binance Trading Bot API is running'
        },
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def trading_session_status(request):
    """
    Get current trading session status with times in multiple timezones.

    GET /api/trading-session/

    Returns:
        - is_active: Whether trading is currently active
        - next_window: Next trading window (if inactive)
        - current_time: Current time in NPT, UTC, and US EST/EDT
        - trading_windows: List of trading windows in all timezones
    """
    utc_now, nepal_now, us_now, is_dst = get_timezone_times()
    is_active = is_within_trading_window()

    response_data = {
        'is_active': is_active,
        'next_window': None if is_active else get_next_window(),
        'current_time': {
            'npt': nepal_now.strftime('%Y-%m-%d %H:%M:%S'),
            'npt_formatted': nepal_now.strftime('%I:%M:%S %p'),
            'utc': utc_now.strftime('%Y-%m-%d %H:%M:%S'),
            'utc_formatted': utc_now.strftime('%I:%M:%S %p'),
            'us': us_now.strftime('%Y-%m-%d %H:%M:%S'),
            'us_formatted': us_now.strftime('%I:%M:%S %p'),
            'us_timezone': 'EDT' if is_dst else 'EST',
        },
        'trading_windows': [
            {
                'window': 1,
                'npt': '17:00 - 18:00',
                'utc': '11:15 - 12:15',
                'us': '06:15 - 07:15 EST / 07:15 - 08:15 EDT',
            },
            {
                'window': 2,
                'npt': '21:00 - 23:00',
                'utc': '15:15 - 17:15',
                'us': '10:15 - 12:15 EST / 11:15 - 13:15 EDT',
            },
        ],
        'timezone_info': {
            'npt_offset': '+05:45',
            'utc_offset': '+00:00',
            'us_offset': '-04:00' if is_dst else '-05:00',
            'us_dst_active': is_dst,
        }
    }

    return Response(response_data, status=status.HTTP_200_OK)
