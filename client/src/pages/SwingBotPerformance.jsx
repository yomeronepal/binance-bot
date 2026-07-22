import BotPerformance from './BotPerformance';

const SWING_SOURCE = {
  title: 'Swing Bot (4h)',
  subtitle: '4h breakout · 1D trend + ADX gate — paper validation ($100 margin · 10x)',
  summaryUrl: '/swing/summary/',
  positionsUrl: '/swing/positions/',
  listUrl: '/swing/trades/',
  closeUrl: (id) => `/swing/trades/${id}/close/`,
  storagePrefix: 'swing_perf_',
  features: { filters: true, windowFilters: false, sessionWindows: false, export: false, report: false, graphs: false, replay: false },
};

const SwingBotPerformance = () => <BotPerformance source={SWING_SOURCE} />;

export default SwingBotPerformance;
