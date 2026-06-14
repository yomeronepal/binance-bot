import BotPerformance from './BotPerformance';

const DAYTRADE_SOURCE = {
  title: 'Day-Trade Bot',
  subtitle: '15m Market Structure Pullback — automated paper trading ($100 margin · 10x)',
  summaryUrl: '/daytrade/summary/',
  positionsUrl: '/daytrade/positions/',
  listUrl: '/daytrade/trades/',
  exportUrl: '/daytrade/export/',
  reportUrl: '/daytrade/report/',
  closeUrl: (id) => `/daytrade/trades/${id}/close/`,
  features: { filters: false, export: false, report: false, graphs: false, replay: false },
};

const DayTradeBotPerformance = () => <BotPerformance source={DAYTRADE_SOURCE} />;

export default DayTradeBotPerformance;
