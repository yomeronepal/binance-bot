/**
 * TradingView Chart Widget Component
 * Embeds a TradingView chart for a given symbol
 */
import { useEffect, useRef, memo } from 'react';

const TradingViewWidget = memo(({ symbol, theme = 'dark', interval = '60', isFutures = false }) => {
    const container = useRef(null);

    useEffect(() => {
        // Clean and format symbol
        let cleanSymbol = (symbol || 'BTCUSDT').toUpperCase().trim();

        // Remove any existing exchange prefix
        if (cleanSymbol.includes(':')) {
            cleanSymbol = cleanSymbol.split(':')[1];
        }

        // Ensure USDT suffix
        if (!cleanSymbol.endsWith('USDT')) {
            cleanSymbol = cleanSymbol + 'USDT';
        }

        // Use spot symbol format for all - TradingView has better support for spot pairs
        // Futures perpetual symbols (.P) don't work for all coins on TradingView
        const tvSymbol = `BINANCE:${cleanSymbol}`;

        // Clear previous widget if exists
        if (container.current) {
            container.current.innerHTML = '';
        }

        // Create widget container div
        const widgetDiv = document.createElement('div');
        widgetDiv.className = 'tradingview-widget-container__widget';
        widgetDiv.style.height = '100%';
        widgetDiv.style.width = '100%';

        const script = document.createElement('script');
        script.src = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
        script.type = 'text/javascript';
        script.async = true;
        script.innerHTML = JSON.stringify({
            autosize: true,
            symbol: tvSymbol,
            interval: interval,
            timezone: 'Etc/UTC',
            theme: theme,
            style: '1',
            locale: 'en',
            enable_publishing: false,
            withdateranges: true,
            hide_side_toolbar: false,
            allow_symbol_change: true,
            details: true,
            hotlist: false,
            calendar: false,
            studies: [
                'STD;RSI',
                'STD;MACD',
            ],
            support_host: 'https://www.tradingview.com',
        });

        if (container.current) {
            container.current.appendChild(widgetDiv);
            container.current.appendChild(script);
        }

        return () => {
            if (container.current) {
                container.current.innerHTML = '';
            }
        };
    }, [symbol, theme, interval, isFutures]);

    return (
        <div
            className="tradingview-widget-container"
            ref={container}
            style={{ height: '100%', width: '100%' }}
        />
    );
});

TradingViewWidget.displayName = 'TradingViewWidget';

export default TradingViewWidget;

