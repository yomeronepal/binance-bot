"""
API views for market data (order book, etc.)
"""
import logging
import asyncio
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_order_book(request, symbol):
    """
    Get order book (market depth) for a symbol.
    
    GET /api/market/orderbook/<symbol>/
    Query params:
        - limit: Number of levels (default: 50, max: 500)
    
    Returns aggregated bids/asks with liquidity calculations.
    """
    try:
        from scanner.services.binance_client import BinanceClient
        
        limit = min(int(request.query_params.get('limit', 50)), 500)
        
        # Ensure symbol format
        symbol = symbol.upper()
        if not symbol.endswith('USDT'):
            symbol = f"{symbol}USDT"
        
        async def fetch_orderbook():
            async with BinanceClient() as client:
                data = await client.get_order_book(symbol, limit=limit)
                price_data = await client.get_price(symbol)
                return data, float(price_data.get('price', 0))

        orderbook, current_price = asyncio.run(fetch_orderbook())
        
        # Process bids and asks
        bids = []
        asks = []
        total_bid_volume = 0
        total_ask_volume = 0
        
        for price, qty in orderbook.get('bids', []):
            price = float(price)
            qty = float(qty)
            total_bid_volume += qty
            bids.append({
                'price': price,
                'quantity': qty,
                'total': price * qty,
            })
        
        for price, qty in orderbook.get('asks', []):
            price = float(price)
            qty = float(qty)
            total_ask_volume += qty
            asks.append({
                'price': price,
                'quantity': qty,
                'total': price * qty,
            })
        
        # Find support/resistance levels (large orders)
        max_bid_volume = max(b['quantity'] for b in bids) if bids else 0
        max_ask_volume = max(a['quantity'] for a in asks) if asks else 0
        
        # Calculate cumulative volumes for heatmap intensity
        cumulative_bid = 0
        for bid in bids:
            cumulative_bid += bid['quantity']
            bid['cumulative'] = cumulative_bid
            bid['intensity'] = bid['quantity'] / max_bid_volume if max_bid_volume > 0 else 0
        
        cumulative_ask = 0
        for ask in asks:
            cumulative_ask += ask['quantity']
            ask['cumulative'] = cumulative_ask
            ask['intensity'] = ask['quantity'] / max_ask_volume if max_ask_volume > 0 else 0
        
        # Find significant walls (> 50% of max volume)
        bid_walls = [b for b in bids if b['intensity'] > 0.5]
        ask_walls = [a for a in asks if a['intensity'] > 0.5]
        
        return Response({
            'symbol': symbol,
            'current_price': current_price,
            'bids': bids[:50],  # Return top 50
            'asks': asks[:50],  # Return top 50
            'summary': {
                'total_bid_volume': total_bid_volume,
                'total_ask_volume': total_ask_volume,
                'bid_ask_ratio': total_bid_volume / total_ask_volume if total_ask_volume > 0 else 0,
                'bid_walls': len(bid_walls),
                'ask_walls': len(ask_walls),
                'strongest_bid': max(bids, key=lambda x: x['quantity'])['price'] if bids else 0,
                'strongest_ask': min(asks, key=lambda x: x['quantity'])['price'] if asks else 0,
            },
            'walls': {
                'bids': bid_walls[:5],  # Top 5 bid walls
                'asks': ask_walls[:5],  # Top 5 ask walls
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching order book for {symbol}: {e}")
        return Response(
            {'error': 'Failed to fetch order book'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
