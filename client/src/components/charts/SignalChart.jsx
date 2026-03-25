import { useEffect, useRef, useState, useCallback } from 'react';
import { createChart, ColorType, LineStyle } from 'lightweight-charts';
import { Loader, BarChart3 } from 'lucide-react';
import api from '../../services/api';

const SignalChart = ({ signalId }) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [showIndicator, setShowIndicator] = useState({
    ema9: true, ema21: true, ema50: false,
    bb: true, rsi: true,
  });

  useEffect(() => {
    fetchData();
    return () => {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [signalId]);

  useEffect(() => {
    if (data && !loading && chartContainerRef.current) {
      const timer = setTimeout(() => buildChart(), 200);
      return () => clearTimeout(timer);
    }
  }, [data, loading, showIndicator]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.get(`/public/signal/${signalId}/chart/`);
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load chart');
    } finally {
      setLoading(false);
    }
  };

  const buildChart = useCallback(async () => {
    const container = chartContainerRef.current;
    if (!container || !data?.candles?.length) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }
    container.innerHTML = '';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight || 400,
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#94a3b8',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      rightPriceScale: { borderColor: '#334155' },
      timeScale: { borderColor: '#334155', timeVisible: true },
    });

    const minPrice = Math.min(...data.candles.map(c => c.low).filter(p => p > 0));
    let precision = 2;
    if (minPrice < 0.0001) precision = 8;
    else if (minPrice < 0.01) precision = 6;
    else if (minPrice < 1) precision = 5;
    else if (minPrice < 100) precision = 4;
    const minMove = 1 / Math.pow(10, precision);

    const candleOpts = {
      upColor: '#22c55e', downColor: '#ef4444',
      borderUpColor: '#22c55e', borderDownColor: '#ef4444',
      wickUpColor: '#22c55e', wickDownColor: '#ef4444',
      priceFormat: { type: 'price', precision, minMove },
    };

    let candleSeries;
    if (chart.addCandlestickSeries) {
      candleSeries = chart.addCandlestickSeries(candleOpts);
    } else {
      const lc = await import('lightweight-charts');
      candleSeries = chart.addSeries(lc.CandlestickSeries, candleOpts);
    }
    candleSeries.setData(data.candles);

    const addLine = async (lineData, color, lineWidth = 1, lineStyle = 0) => {
      const opts = { color, lineWidth, lineStyle, priceLineVisible: false, lastValueVisible: false };
      let series;
      if (chart.addLineSeries) {
        series = chart.addLineSeries(opts);
      } else {
        const lc = await import('lightweight-charts');
        series = chart.addSeries(lc.LineSeries, opts);
      }
      series.setData(lineData);
    };

    const ind = data.indicators || {};
    if (showIndicator.ema9 && ind.ema9?.length) await addLine(ind.ema9, '#f59e0b', 1);
    if (showIndicator.ema21 && ind.ema21?.length) await addLine(ind.ema21, '#8b5cf6', 1);
    if (showIndicator.ema50 && ind.ema50?.length) await addLine(ind.ema50, '#06b6d4', 1);
    if (showIndicator.bb && ind.bb_upper?.length) {
      await addLine(ind.bb_upper, '#64748b', 1, LineStyle.Dotted);
      await addLine(ind.bb_mid, '#64748b', 1, LineStyle.Dashed);
      await addLine(ind.bb_lower, '#64748b', 1, LineStyle.Dotted);
    }

    if (data.markers?.length) candleSeries.setMarkers(data.markers);

    (data.lines || []).forEach(line => {
      candleSeries.createPriceLine({
        price: line.price,
        color: line.color,
        lineWidth: line.lineWidth || 1,
        lineStyle: line.lineStyle === 2 ? LineStyle.Dashed : line.lineStyle === 1 ? LineStyle.Dotted : LineStyle.Solid,
        axisLabelVisible: true,
        title: line.title,
      });
    });

    chart.timeScale().fitContent();
    chartRef.current = chart;

    const onResize = () => chart.applyOptions({ width: container.clientWidth });
    window.addEventListener('resize', onResize);
  }, [data, showIndicator]);

  const toggleIndicator = (key) => setShowIndicator(prev => ({ ...prev, [key]: !prev[key] }));

  if (loading) {
    return (
      <div className="bg-slate-900/50 rounded-xl border border-slate-700/50 p-8 flex items-center justify-center gap-2">
        <Loader className="w-5 h-5 animate-spin text-blue-500" />
        <span className="text-slate-400 text-sm">Loading chart...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-900/50 rounded-xl border border-slate-700/50 p-6 text-center">
        <BarChart3 className="w-8 h-8 text-slate-600 mx-auto mb-2" />
        <p className="text-slate-500 text-sm">{error}</p>
      </div>
    );
  }

  const sig = data?.signal;
  const indicators = [
    { key: 'ema9', label: 'EMA 9', color: '#f59e0b' },
    { key: 'ema21', label: 'EMA 21', color: '#8b5cf6' },
    { key: 'ema50', label: 'EMA 50', color: '#06b6d4' },
    { key: 'bb', label: 'BB', color: '#64748b' },
    { key: 'rsi', label: 'RSI', color: '#a855f7' },
  ];

  const rsiData = data?.indicators?.rsi || [];

  return (
    <div className="bg-slate-900/50 rounded-xl border border-slate-700/50 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700/50">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-medium text-white">{sig?.symbol} {sig?.timeframe}</span>
          <span className="text-[10px] text-slate-500">{data?.candles?.length} candles</span>
        </div>
        <div className="flex items-center gap-1">
          {indicators.map(ind => (
            <button key={ind.key} onClick={() => toggleIndicator(ind.key)}
              className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                showIndicator[ind.key] ? 'text-white' : 'text-slate-600 hover:text-slate-400'
              }`}
              style={showIndicator[ind.key] ? { backgroundColor: ind.color + '30', color: ind.color } : {}}>
              {ind.label}
            </button>
          ))}
        </div>
      </div>

      <div ref={chartContainerRef} style={{ width: '100%', height: '400px' }} />

      {showIndicator.rsi && rsiData.length > 0 && (
        <div className="border-t border-slate-700/50 px-4 py-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-slate-500 uppercase">RSI (14)</span>
            <span className={`text-xs font-mono font-bold ${
              rsiData[rsiData.length - 1]?.value > 70 ? 'text-rose-400' :
              rsiData[rsiData.length - 1]?.value < 30 ? 'text-emerald-400' : 'text-slate-400'
            }`}>
              {rsiData[rsiData.length - 1]?.value?.toFixed(1)}
            </span>
          </div>
          <div className="h-12 flex items-end gap-px">
            {rsiData.slice(-60).map((d, i) => {
              const h = (d.value / 100) * 100;
              const color = d.value > 70 ? '#ef4444' : d.value < 30 ? '#22c55e' : '#64748b';
              return <div key={i} className="flex-1 rounded-t-sm" style={{ height: `${h}%`, backgroundColor: color + '60', minWidth: '1px' }} />;
            })}
          </div>
          <div className="flex justify-between text-[9px] text-slate-600 mt-0.5">
            <span>30</span><span>50</span><span>70</span>
          </div>
        </div>
      )}

      {sig?.meta && Object.keys(sig.meta).length > 0 && (
        <div className="border-t border-slate-700/50 px-4 py-2">
          <span className="text-[10px] text-slate-500 uppercase block mb-1">Confluence</span>
          <div className="flex flex-wrap gap-1">
            {Object.entries(sig.meta).map(([key, val]) => (
              <span key={key} className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded">
                {key}: {typeof val === 'object' ? JSON.stringify(val) : String(val)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SignalChart;
