"""
Celery Tasks for Backtesting
Async tasks for running backtests, optimizations, and generating recommendations.
"""
import logging
import asyncio
from celery import shared_task
from datetime import datetime
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def run_backtest_async(self, backtest_id: int):
    """
    Run a backtest asynchronously.

    Args:
        backtest_id: ID of BacktestRun to execute

    Returns:
        Dictionary with backtest results
    """
    from signals.models_backtest import BacktestRun, BacktestTrade, BacktestMetric
    from scanner.services.historical_data_fetcher import historical_data_fetcher
    from scanner.services.backtest_engine import BacktestEngine
    from scanner.strategies.signal_engine import SignalDetectionEngine, SignalConfig

    try:
        logger.info(f"📊 Starting backtest {backtest_id}")

        # Get backtest run
        backtest_run = BacktestRun.objects.get(id=backtest_id)
        backtest_run.status = 'RUNNING'
        backtest_run.started_at = timezone.now()
        backtest_run.save()

        # Fetch historical data
        logger.info(f"Fetching historical data for {len(backtest_run.symbols)} symbols...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Use CSV loader first (faster and uses local data)
            symbols_data = loop.run_until_complete(
                historical_data_fetcher.fetch_multiple_symbols_from_csv(
                    backtest_run.symbols,
                    backtest_run.timeframe,
                    backtest_run.start_date,
                    backtest_run.end_date,
                    data_dir="backtest_data"  # Use local CSV files
                )
            )
        finally:
            loop.close()

        if not symbols_data:
            raise Exception("No historical data fetched")

        logger.info(f"Fetched data for {len(symbols_data)} symbols")

        # Generate signals using strategy
        logger.info("Generating signals from historical data...")
        signal_config = _dict_to_signal_config(backtest_run.strategy_params)

        # IMPORTANT: Disable volatility-aware mode to respect custom parameters
        # Volatility-aware mode overrides sl_atr_multiplier, tp_atr_multiplier, adx_min, and min_confidence
        # which prevents us from testing different parameter combinations
        engine = SignalDetectionEngine(signal_config, use_volatility_aware=False)
        logger.info("Signal engine initialized (volatility-aware mode DISABLED for parameter testing)")

        signals = []
        for symbol, klines in symbols_data.items():
            if not klines:
                continue

            logger.info(f"Processing {symbol} with {len(klines)} candles...")

            # Process candles sequentially to simulate real-time signal generation
            # Add candles one by one and check for signals after each
            for i, candle in enumerate(klines):
                # Add current candle to engine
                engine.update_candles(symbol, [candle])

                # Only start checking for signals after we have enough candles for indicators (50+)
                if i < 50:
                    continue

                # Check if signal is generated
                result = engine.process_symbol(symbol, backtest_run.timeframe)
                if result and result.get('action') == 'created':
                    signal_data = result['signal']
                    # Get timestamp - handle both dict and list formats
                    if isinstance(candle, dict):
                        timestamp = candle.get('timestamp')
                    else:
                        timestamp = candle[0]  # Array format

                    signals.append({
                        'symbol': symbol,
                        'timestamp': timestamp,
                        'direction': signal_data['direction'],
                        'entry': signal_data['entry'],
                        'tp': signal_data['tp'],
                        'sl': signal_data['sl'],
                        'confidence': signal_data.get('confidence', 0.7),
                        'indicators': signal_data.get('conditions_met', {})
                    })
                    logger.info(f"✅ Signal generated for {symbol}: {signal_data['direction']} @ {signal_data['entry']}")

        logger.info(f"Generated {len(signals)} signals across {len(symbols_data)} symbols")

        # Run backtest
        logger.info("Running backtest simulation...")
        backtest_engine = BacktestEngine(
            initial_capital=backtest_run.initial_capital,
            position_size=backtest_run.position_size,
            strategy_params=backtest_run.strategy_params
        )

        results = backtest_engine.run_backtest(symbols_data, signals)

        # Save results
        logger.info("Saving backtest results...")

        # Update backtest run with metrics
        backtest_run.total_trades = results['total_trades']
        backtest_run.winning_trades = results['winning_trades']
        backtest_run.losing_trades = results['losing_trades']
        backtest_run.win_rate = results['win_rate']
        backtest_run.total_profit_loss = results['total_profit_loss']
        backtest_run.roi = results['roi']
        backtest_run.max_drawdown = results['max_drawdown']
        backtest_run.max_drawdown_percentage = results['max_drawdown_percentage']
        backtest_run.avg_trade_duration_hours = results['avg_trade_duration_hours']
        backtest_run.avg_profit_per_trade = results['avg_profit_per_trade']
        backtest_run.sharpe_ratio = results.get('sharpe_ratio')
        backtest_run.profit_factor = results.get('profit_factor')
        backtest_run.equity_curve = results.get('equity_curve', [])
        backtest_run.status = 'COMPLETED'
        backtest_run.completed_at = timezone.now()
        backtest_run.save()

        # Save trades
        for trade_data in results['closed_trades']:
            BacktestTrade.objects.create(
                backtest_run=backtest_run,
                symbol=trade_data['symbol'],
                direction=trade_data['direction'],
                market_type='SPOT',
                entry_price=trade_data['entry_price'],
                exit_price=trade_data['exit_price'],
                stop_loss=trade_data['stop_loss'],
                take_profit=trade_data['take_profit'],
                position_size=trade_data['position_size'],
                quantity=trade_data['quantity'],
                leverage=trade_data.get('leverage'),
                profit_loss=trade_data['profit_loss'],
                profit_loss_percentage=trade_data['profit_loss_percentage'],
                opened_at=trade_data['opened_at'],
                closed_at=trade_data['closed_at'],
                duration_hours=trade_data['duration_hours'],
                status=trade_data['status'],
                signal_confidence=trade_data.get('signal_confidence'),
                signal_indicators=trade_data.get('signal_indicators', {}),
                risk_reward_ratio=trade_data.get('risk_reward_ratio')
            )

        logger.info(
            f"✅ Backtest {backtest_id} completed: "
            f"{results['total_trades']} trades, "
            f"{float(results['win_rate']):.2f}% win rate, "
            f"{float(results['roi']):.2f}% ROI"
        )

        return {
            'backtest_id': backtest_id,
            'status': 'COMPLETED',
            'total_trades': results['total_trades'],
            'win_rate': float(results['win_rate']),
            'roi': float(results['roi'])
        }

    except Exception as exc:
        logger.error(f"❌ Backtest {backtest_id} failed: {exc}", exc_info=True)

        # Update status
        try:
            backtest_run = BacktestRun.objects.get(id=backtest_id)
            backtest_run.status = 'FAILED'
            backtest_run.error_message = str(exc)
            backtest_run.completed_at = timezone.now()
            backtest_run.save()
        except:
            pass

        # Retry
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=300)
def run_optimization_async(
    self,
    user_id: int,
    name: str,
    symbols: list,
    timeframe: str,
    start_date: str,
    end_date: str,
    parameter_ranges: dict,
    search_method: str = 'grid',
    max_combinations: int = 100
):
    """
    Run parameter optimization asynchronously.

    Args:
        user_id: User ID
        name: Optimization name
        symbols: List of symbols
        timeframe: Timeframe
        start_date: Start date (ISO format string)
        end_date: End date (ISO format string)
        parameter_ranges: Dict of param name to list of values
        search_method: 'grid' or 'random'
        max_combinations: Max combinations for random search

    Returns:
        Dictionary with optimization results
    """
    from django.contrib.auth import get_user_model
    from signals.models_backtest import StrategyOptimization, BacktestRun
    from scanner.services.parameter_optimizer import parameter_optimizer

    User = get_user_model()

    try:
        logger.info(f"🔍 Starting optimization: {name}")

        user = User.objects.get(id=user_id)

        # Parse dates
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        # Run optimization
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            results = loop.run_until_complete(
                parameter_optimizer.optimize_parameters(
                    symbols=symbols,
                    timeframe=timeframe,
                    start_date=start_dt,
                    end_date=end_dt,
                    parameter_ranges=parameter_ranges,
                    search_method=search_method,
                    max_combinations=max_combinations
                )
            )
        finally:
            loop.close()

        logger.info(f"Tested {len(results)} combinations")

        # Save top results to database
        saved_count = 0
        for result in results[:20]:  # Save top 20
            try:
                StrategyOptimization.objects.create(
                    name=f"{name} - Combination {result['combination_id']}",
                    user=user,
                    symbols=symbols,
                    timeframe=timeframe,
                    date_range_start=start_dt,
                    date_range_end=end_dt,
                    params=result['params'],
                    total_trades=result['total_trades'],
                    win_rate=result['win_rate'],
                    roi=result['roi'],
                    total_profit_loss=result['total_profit_loss'],
                    max_drawdown=result.get('max_drawdown', Decimal('0')),
                    sharpe_ratio=result.get('sharpe_ratio'),
                    profit_factor=result.get('profit_factor'),
                    optimization_score=result['optimization_score']
                )
                saved_count += 1
            except Exception as e:
                logger.error(f"Error saving optimization result: {e}")

        logger.info(f"✅ Optimization complete: saved {saved_count} results")

        best = results[0] if results else None

        return {
            'name': name,
            'total_combinations': len(results),
            'saved_results': saved_count,
            'best_result': {
                'params': best['params'],
                'win_rate': float(best['win_rate']),
                'roi': float(best['roi']),
                'score': float(best['optimization_score'])
            } if best else None
        }

    except Exception as exc:
        logger.error(f"❌ Optimization failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, default_retry_delay=180)
def generate_recommendations_async(
    self,
    user_id: int,
    lookback_days: int = 90,
    min_samples: int = 10
):
    """
    Generate AI recommendations based on optimization history.

    Args:
        user_id: User ID
        lookback_days: Days of history to analyze
        min_samples: Minimum optimizations needed

    Returns:
        Dictionary with recommendation results
    """
    from django.contrib.auth import get_user_model
    from scanner.services.self_learning_module import self_learning_module

    User = get_user_model()

    try:
        logger.info(f"🤖 Generating recommendations for user {user_id}")

        user = User.objects.get(id=user_id)

        # Analyze and generate recommendations
        recommendations = self_learning_module.analyze_and_recommend(
            user=user,
            lookback_days=lookback_days,
            min_samples=min_samples
        )

        # Save recommendations
        saved_recommendations = self_learning_module.save_recommendations(
            recommendations,
            user=user
        )

        logger.info(f"✅ Generated {len(saved_recommendations)} recommendations")

        return {
            'user_id': user_id,
            'recommendations_count': len(saved_recommendations),
            'recommendations': [
                {
                    'id': rec.id,
                    'type': rec.type,
                    'title': rec.title,
                    'confidence': float(rec.confidence_score)
                }
                for rec in saved_recommendations
            ]
        }

    except Exception as exc:
        logger.error(f"❌ Recommendation generation failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)


def _dict_to_signal_config(params: dict):
    """Convert parameter dict to SignalConfig."""
    from scanner.strategies.signal_engine import SignalConfig

    config = SignalConfig()

    param_mapping = {
        'long_rsi_min': 'long_rsi_min',
        'long_rsi_max': 'long_rsi_max',
        'short_rsi_min': 'short_rsi_min',
        'short_rsi_max': 'short_rsi_max',
        'long_adx_min': 'long_adx_min',
        'short_adx_min': 'short_adx_min',
        'sl_atr_multiplier': 'sl_atr_multiplier',
        'tp_atr_multiplier': 'tp_atr_multiplier',
        'min_confidence': 'min_confidence',
    }

    for param_key, config_key in param_mapping.items():
        if param_key in params:
            setattr(config, config_key, params[param_key])

    return config
