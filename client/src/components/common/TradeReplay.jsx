import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, LineStyle } from 'lightweight-charts';
import { X, Loader, Play, Pause, RotateCcw, TrendingUp, TrendingDown } from 'lucide-react';
import api from '../../services/api';
import useThemeStore from '../../store/useThemeStore';

const formatPrice = (price) => {
  if (!price || price === 0) return '0';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (num >= 1000) return num.toFixed(2);
  if (num >= 1) return num.toFixed(4);
  if (num >= 0.01) return num.toFixed(6);
  return num.toFixed(8);
};

const TradeReplay = ({ tradeId, onClose }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tradeData, setTradeData] = useState(null);
  const [allCandles, setAllCandles] = useState([]);
  const [allMarkers, setAllMarkers] = useState([]);
  const [allLines, setAllLines] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(100);
  const [visibleCount, setVisibleCount] = useState(0);
  const playRef = useRef(null);
  const [chartReady, setChartReady] = useState(false);
  const { theme } = useThemeStore();
  const isDark = theme === 'dark';

  useEffect(() => {
    loadData();
    return () => {
      clearInterval(playRef.current);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [tradeId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      setChartReady(false);
      const res = await api.get(`/public/paper-trading/${tradeId}/replay/`);
      setTradeData(res.data.trade);
      setAllCandles(res.data.candles || []);
      setAllMarkers(res.data.markers || []);
      setAllLines(res.data.lines || []);
      setVisibleCount(res.data.candles?.length || 0);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load trade data');
    } finally {
      setLoading(false);
    }
  };

  const buildChart = useCallback(async () => {
    const container = chartContainerRef.current;
    if (!container || allCandles.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    container.innerHTML = '';
    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: isDark ? '#111827' : '#ffffff' },
        textColor: isDark ? '#9ca3af' : '#475569',
      },
      grid: {
        vertLines: { color: isDark ? '#1f2937' : '#f1f5f9' },
        horzLines: { color: isDark ? '#1f2937' : '#f1f5f9' },
      },
      rightPriceScale: { borderColor: isDark ? '#374151' : '#e2e8f0', entireTextOnly: true },
      timeScale: { borderColor: isDark ? '#374151' : '#e2e8f0', timeVisible: true },
    });

    const minPrice = Math.min(...allCandles.map(c => c.low).filter(p => p > 0));
    let precision = 2;
    if (minPrice < 0.0001) precision = 8;
    else if (minPrice < 0.01) precision = 6;
    else if (minPrice < 1) precision = 5;
    else if (minPrice < 100) precision = 4;
    const minMove = 1 / Math.pow(10, precision);

    const candleOpts = {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      priceFormat: { type: 'price', precision, minMove },
    };
    const volumeOpts = {
      color: '#3b82f680',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    };

    let candleSeries, volumeSeries;
    if (chart.addCandlestickSeries) {
      candleSeries = chart.addCandlestickSeries(candleOpts);
      volumeSeries = chart.addHistogramSeries(volumeOpts);
    } else {
      const lc = await import('lightweight-charts');
      candleSeries = chart.addSeries(lc.CandlestickSeries, candleOpts);
      volumeSeries = chart.addSeries(lc.HistogramSeries, volumeOpts);
    }
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    console.log('[TradeReplay] Setting candle data:', allCandles.length, 'candles, container:', container.clientWidth, 'x', container.clientHeight, 'first:', allCandles[0]);
    candleSeries.setData(allCandles);
    volumeSeries.setData(allCandles.map(c => ({
      time: c.time,
      value: c.volume,
      color: c.close >= c.open ? '#22c55e40' : '#ef444440',
    })));

    if (allMarkers.length > 0) {
      candleSeries.setMarkers(allMarkers);
    }

    allLines.forEach(line => {
      candleSeries.createPriceLine({
        price: line.price,
        color: line.color,
        lineWidth: line.lineWidth || 1,
        lineStyle: line.lineStyle === 2 ? LineStyle.Dashed : LineStyle.Solid,
        axisLabelVisible: true,
        title: line.title,
      });
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    setChartReady(true);

    chart.timeScale().fitContent();

    const onResize = () => {
      chart.applyOptions({ width: container.clientWidth });
    };
    window.addEventListener('resize', onResize);

    setTimeout(() => {
      chart.applyOptions({ width: container.clientWidth });
      chart.timeScale().fitContent();
    }, 100);
  }, [allCandles, allMarkers, allLines]);

  useEffect(() => {
    if (loading || allCandles.length === 0 || chartReady) return;
    const container = chartContainerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry && entry.contentRect.width > 100) {
        observer.disconnect();
        buildChart();
      }
    });
    observer.observe(container);

    const fallback = setTimeout(() => {
      observer.disconnect();
      if (!chartReady) buildChart();
    }, 500);

    return () => {
      observer.disconnect();
      clearTimeout(fallback);
    };
  }, [loading, allCandles, chartReady, buildChart]);

  const startReplay = () => {
    if (isPlaying) {
      clearInterval(playRef.current);
      setIsPlaying(false);
      return;
    }

    setIsPlaying(true);
    let count = 0;

    candleSeriesRef.current?.setData([]);
    volumeSeriesRef.current?.setData([]);
    candleSeriesRef.current?.setMarkers([]);

    playRef.current = setInterval(() => {
      count++;
      if (count >= allCandles.length) {
        clearInterval(playRef.current);
        setIsPlaying(false);
        candleSeriesRef.current?.setMarkers(allMarkers);
        setVisibleCount(allCandles.length);
        return;
      }

      const slice = allCandles.slice(0, count + 1);
      candleSeriesRef.current?.setData(slice);
      volumeSeriesRef.current?.setData(slice.map(c => ({
        time: c.time,
        value: c.volume,
        color: c.close >= c.open ? '#22c55e40' : '#ef444440',
      })));

      setVisibleCount(count + 1);

      if (tradeData) {
        const entryTs = new Date(tradeData.entry_time).getTime() / 1000;
        const exitTs = tradeData.exit_time ? new Date(tradeData.exit_time).getTime() / 1000 : Infinity;
        const lastTs = slice[slice.length - 1].time;

        const m = [];
        if (lastTs >= entryTs) {
          const closest = slice.reduce((a, b) => Math.abs(a.time - entryTs) < Math.abs(b.time - entryTs) ? a : b);
          m.push({
            time: closest.time,
            position: tradeData.direction === 'LONG' ? 'belowBar' : 'aboveBar',
            color: '#22c55e',
            shape: tradeData.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
            text: 'ENTRY',
          });
        }
        if (lastTs >= exitTs && tradeData.exit_time) {
          const closest = slice.reduce((a, b) => Math.abs(a.time - exitTs) < Math.abs(b.time - exitTs) ? a : b);
          m.push({
            time: closest.time,
            position: tradeData.direction === 'LONG' ? 'aboveBar' : 'belowBar',
            color: (tradeData.profit_loss || 0) >= 0 ? '#22c55e' : '#ef4444',
            shape: tradeData.direction === 'LONG' ? 'arrowDown' : 'arrowUp',
            text: 'EXIT',
          });
        }
        if (m.length) candleSeriesRef.current?.setMarkers(m.sort((a, b) => a.time - b.time));
      }
    }, speed);
  };

  const resetChart = () => {
    clearInterval(playRef.current);
    setIsPlaying(false);
    if (candleSeriesRef.current) {
      candleSeriesRef.current.setData(allCandles);
      volumeSeriesRef.current?.setData(allCandles.map(c => ({
        time: c.time, value: c.volume,
        color: c.close >= c.open ? '#22c55e40' : '#ef444440',
      })));
      candleSeriesRef.current.setMarkers(allMarkers);
      chartRef.current?.timeScale().fitContent();
      setVisibleCount(allCandles.length);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
        <div className="bg-white dark:bg-gray-900 rounded-xl p-8 flex items-center gap-3 shadow-2xl">
          <Loader className="w-5 h-5 animate-spin text-blue-500" />
          <span className="text-gray-600 dark:text-gray-300">Loading trade replay...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
        <div className="bg-gray-900 rounded-xl p-6 max-w-md">
          <p className="text-red-400 mb-4">{error}</p>
          <button onClick={onClose} className="px-4 py-2 bg-gray-700 text-white rounded-lg">Close</button>
        </div>
      </div>
    );
  }

  const trade = tradeData;
  const isLong = trade?.direction === 'LONG';
  const pnl = trade?.profit_loss || 0;
  const isWin = pnl >= 0;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 dark:bg-black/80 flex items-center justify-center p-2 sm:p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-900 rounded-xl w-full max-w-4xl overflow-hidden flex flex-col shadow-2xl m-auto" style={{ maxHeight: '85vh' }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3 flex-wrap">
            {isLong ? <TrendingUp className="w-5 h-5 text-emerald-500" /> : <TrendingDown className="w-5 h-5 text-rose-500" />}
            <h3 className="font-bold text-gray-900 dark:text-white">{trade?.symbol}</h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${isLong ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
              {trade?.direction}
            </span>
            <span className="text-xs text-gray-400">{trade?.timeframe}</span>
            <span className={`text-sm font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(4)} USDT
            </span>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-800 rounded-lg">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/50">
          <button onClick={startReplay}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white shadow-sm">
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {isPlaying ? 'Pause' : 'Replay'}
          </button>
          <button onClick={resetChart}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-white">
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
          <div className="flex items-center gap-1 ml-2">
            <span className="text-[10px] text-gray-500">SPEED</span>
            {[{ ms: 200, label: '0.5x' }, { ms: 100, label: '1x' }, { ms: 50, label: '2x' }, { ms: 20, label: '5x' }].map(s => (
              <button key={s.ms} onClick={() => setSpeed(s.ms)}
                className={`px-2 py-1 rounded text-[10px] font-medium ${speed === s.ms ? 'bg-blue-600 text-white' : 'bg-gray-200 dark:bg-gray-800 text-gray-600 dark:text-gray-400'}`}>
                {s.label}
              </button>
            ))}
          </div>
          <span className="ml-auto text-[10px] text-gray-500">{visibleCount}/{allCandles.length} candles</span>
        </div>

        <div ref={chartContainerRef} style={{ width: '100%', height: '400px', minHeight: '400px' }} />

        <div className="grid grid-cols-4 gap-px bg-gray-200 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-800">
          <div className="bg-white dark:bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-gray-500">Entry</div>
            <div className="text-sm font-mono text-blue-400">${trade?.entry_price ? formatPrice(trade.entry_price) : '-'}</div>
          </div>
          <div className="bg-white dark:bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-gray-500">Exit</div>
            <div className={`text-sm font-mono ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
              {trade?.exit_price ? `$${formatPrice(trade.exit_price)}` : '-'}
            </div>
          </div>
          <div className="bg-white dark:bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-rose-400">Stop Loss</div>
            <div className="text-sm font-mono text-rose-400">{trade?.stop_loss ? `$${formatPrice(trade.stop_loss)}` : '-'}</div>
          </div>
          <div className="bg-white dark:bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-emerald-400">Take Profit</div>
            <div className="text-sm font-mono text-emerald-400">{trade?.take_profit ? `$${formatPrice(trade.take_profit)}` : '-'}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradeReplay;
