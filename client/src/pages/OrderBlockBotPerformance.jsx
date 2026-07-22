import BotPerformance from './BotPerformance';

const ORDER_BLOCK_SOURCE = {
  title: 'Order Block Bot (4h)',
  subtitle: '4h ICT order-block · fixed 2R · 1% risk/trade · max 3 concurrent — paper validation',
  summaryUrl: '/order-block/summary/',
  positionsUrl: '/order-block/positions/',
  listUrl: '/order-block/trades/',
  closeUrl: (id) => `/order-block/trades/${id}/close/`,
  storagePrefix: 'order_block_perf_',
  features: { filters: true, windowFilters: false, sessionWindows: false, export: false, report: false, graphs: false, replay: false },
};

const OrderBlockBotPerformance = () => <BotPerformance source={ORDER_BLOCK_SOURCE} />;

export default OrderBlockBotPerformance;
