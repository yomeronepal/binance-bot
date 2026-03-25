import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, LineStyle } from 'lightweight-charts';
import { X, Loader, Play, Pause, SkipForward, RotateCcw, TrendingUp, TrendingDown } from 'lucide-react';
import api from '../../services/api';

const formatPrice = (price) => {
  if (!price || price === 0) return '0';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (num >= 1000) return num.toFixed(2);
  if (num >= 1) return num.toFixed(4);
  if (num >= 0.01) return num.toFixed(6);
  return num.toFixed(8);
};

const TradeReplay = ({ tradeId, onClose }) => {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tradeData, setTradeData] = useState(null);
  const [allCandles, setAllCandles] = useState([]);
  const [visibleCount, setVisibleCount] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(100);
  const playIntervalRef = useRef(null);

  useEffect(() => {
    fetchReplayData();
    return () => {
      stopPlayback();
      if (chartInstance.current) {
        chartInstance.current.remove();
        chartInstance.current = null;
      }
    };
  }, [tradeId]);

  const fetchReplayData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get(`/public/paper-trading/${tradeId}/replay/`);
      setTradeData(res.data.trade);
      setAllCandles(res.data.candles);
      setVisibleCount(res.data.candles.length);
      setTimeout(() => initChart(res.data), 100);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load trade data');
    } finally {
      setLoading(false);
    }
  };

  const initChart = (data) => {
    if (!chartRef.current) return;
    if (chartInstance.current) {
      chartInstance.current.remove();
    }

    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#111827' },
        textColor: '#9ca3af',
      },
      grid: {
        vertLines: { color: '#1f2937' },
        horzLines: { color: '#1f2937' },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderColor: '#374151',
      },
      timeScale: {
        borderColor: '#374151',
        timeVisible: true,
      },
      width: chartRef.current.clientWidth,
      height: 400,
    });

    const minPrice = Math.min(...data.candles.map(c => c.low));
    const precision = minPrice >= 1000 ? 2 : minPrice >= 1 ? 4 : minPrice >= 0.01 ? 6 : 8;
    const minMove = parseFloat((1 / Math.pow(10, precision)).toFixed(precision));

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderUpColor: '#22c55e',
      borderDownColor: '#ef4444',
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
      priceFormat: { type: 'price', precision, minMove },
    });

    const volumeSeries = chart.addHistogramSeries({
      color: '#3b82f680',
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    data.lines.forEach(line => {
      candleSeries.createPriceLine({
        price: line.price,
        color: line.color,
        lineWidth: line.lineWidth || 1,
        lineStyle: line.lineStyle === 2 ? LineStyle.Dashed : LineStyle.Solid,
        axisLabelVisible: true,
        title: line.title,
      });
    });

    chartInstance.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    candleSeries.setData(data.candles);
    volumeSeries.setData(data.candles.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? '#22c55e40' : '#ef444440' })));
    candleSeries.setMarkers(data.markers);

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (chartRef.current) {
        chart.applyOptions({ width: chartRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  };

  const startPlayback = () => {
    if (isPlaying) return;
    setIsPlaying(true);
    setVisibleCount(1);

    if (candleSeriesRef.current) {
      candleSeriesRef.current.setData([]);
      volumeSeriesRef.current.setData([]);
      candleSeriesRef.current.setMarkers([]);
    }

    let count = 1;
    playIntervalRef.current = setInterval(() => {
      if (count >= allCandles.length) {
        stopPlayback();
        if (tradeData) {
          const markers = buildMarkers(tradeData, allCandles);
          candleSeriesRef.current?.setMarkers(markers);
        }
        return;
      }

      const slice = allCandles.slice(0, count + 1);
      candleSeriesRef.current?.setData(slice);
      volumeSeriesRef.current?.setData(
        slice.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? '#22c55e40' : '#ef444440' }))
      );

      const entryTs = tradeData ? new Date(tradeData.entry_time).getTime() / 1000 : 0;
      const exitTs = tradeData?.exit_time ? new Date(tradeData.exit_time).getTime() / 1000 : 0;
      const lastCandle = slice[slice.length - 1];

      const markers = [];
      if (lastCandle.time >= entryTs) {
        markers.push(...buildMarkers(tradeData, slice, true, lastCandle.time >= exitTs));
      }
      candleSeriesRef.current?.setMarkers(markers);

      count++;
      setVisibleCount(count);
    }, speed);
  };

  const stopPlayback = () => {
    setIsPlaying(false);
    if (playIntervalRef.current) {
      clearInterval(playIntervalRef.current);
      playIntervalRef.current = null;
    }
  };

  const resetChart = () => {
    stopPlayback();
    if (candleSeriesRef.current && allCandles.length > 0) {
      candleSeriesRef.current.setData(allCandles);
      volumeSeriesRef.current.setData(
        allCandles.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? '#22c55e40' : '#ef444440' }))
      );
      const markers = buildMarkers(tradeData, allCandles);
      candleSeriesRef.current.setMarkers(markers);
      chartInstance.current?.timeScale().fitContent();
      setVisibleCount(allCandles.length);
    }
  };

  const buildMarkers = (trade, candles, showEntry = true, showExit = true) => {
    if (!trade || candles.length === 0) return [];
    const markers = [];
    const entryTs = new Date(trade.entry_time).getTime() / 1000;
    const closestEntry = candles.reduce((a, b) => Math.abs(a.time - entryTs) < Math.abs(b.time - entryTs) ? a : b);

    if (showEntry) {
      markers.push({
        time: closestEntry.time,
        position: trade.direction === 'LONG' ? 'belowBar' : 'aboveBar',
        color: '#22c55e',
        shape: trade.direction === 'LONG' ? 'arrowUp' : 'arrowDown',
        text: `ENTRY $${formatPrice(trade.entry_price)}`,
      });
    }

    if (showExit && trade.exit_price && trade.exit_time) {
      const exitTs = new Date(trade.exit_time).getTime() / 1000;
      const closestExit = candles.reduce((a, b) => Math.abs(a.time - exitTs) < Math.abs(b.time - exitTs) ? a : b);
      const isWin = (trade.profit_loss || 0) >= 0;
      markers.push({
        time: closestExit.time,
        position: trade.direction === 'LONG' ? 'aboveBar' : 'belowBar',
        color: isWin ? '#22c55e' : '#ef4444',
        shape: trade.direction === 'LONG' ? 'arrowDown' : 'arrowUp',
        text: `EXIT $${formatPrice(trade.exit_price)}`,
      });
    }

    return markers.sort((a, b) => a.time - b.time);
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center">
        <div className="bg-gray-900 rounded-xl p-8 flex items-center gap-3">
          <Loader className="w-5 h-5 animate-spin text-blue-500" />
          <span className="text-gray-300">Loading trade replay...</span>
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
    <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4">
      <div className="bg-gray-900 rounded-xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
          <div className="flex items-center gap-3">
            {isLong ? <TrendingUp className="w-5 h-5 text-emerald-500" /> : <TrendingDown className="w-5 h-5 text-rose-500" />}
            <h3 className="font-bold text-white">{trade?.symbol}</h3>
            <span className={`text-xs font-bold px-2 py-0.5 rounded ${isLong ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
              {trade?.direction}
            </span>
            <span className="text-xs text-gray-400">{trade?.timeframe}</span>
            <span className={`text-sm font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(4)} USDT
            </span>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-800 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-800 bg-gray-900/50">
          <button onClick={isPlaying ? stopPlayback : startPlayback}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors">
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {isPlaying ? 'Pause' : 'Replay'}
          </button>
          <button onClick={resetChart}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-700 hover:bg-gray-600 text-white transition-colors">
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
          <div className="flex items-center gap-1 ml-2">
            <span className="text-[10px] text-gray-500 uppercase">Speed</span>
            {[200, 100, 50, 20].map(s => (
              <button key={s} onClick={() => { setSpeed(s); if (isPlaying) { stopPlayback(); setTimeout(() => startPlayback(), 50); } }}
                className={`px-2 py-1 rounded text-[10px] font-medium ${speed === s ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}>
                {s === 200 ? '0.5x' : s === 100 ? '1x' : s === 50 ? '2x' : '5x'}
              </button>
            ))}
          </div>
          <div className="ml-auto text-[10px] text-gray-500">
            {visibleCount}/{allCandles.length} candles
          </div>
        </div>

        <div className="flex-1 min-h-0">
          <div ref={chartRef} className="w-full h-[400px]" />
        </div>

        <div className="grid grid-cols-4 gap-px bg-gray-800 border-t border-gray-800">
          <div className="bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-gray-500">Entry</div>
            <div className="text-sm font-mono text-blue-400">${trade?.entry_price ? formatPrice(trade.entry_price) : '0'}</div>
          </div>
          <div className="bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-gray-500">Exit</div>
            <div className={`text-sm font-mono ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
              {trade?.exit_price ? `$${formatPrice(trade.exit_price)}` : '-'}
            </div>
          </div>
          <div className="bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-rose-400">Stop Loss</div>
            <div className="text-sm font-mono text-rose-400">{trade?.stop_loss ? `$${formatPrice(trade.stop_loss)}` : '-'}</div>
          </div>
          <div className="bg-gray-900 px-3 py-2 text-center">
            <div className="text-[10px] text-emerald-400">Take Profit</div>
            <div className="text-sm font-mono text-emerald-400">{trade?.take_profit ? `$${formatPrice(trade.take_profit)}` : '-'}</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TradeReplay;
