import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
    TrendingUp, Activity, Zap, Shield, BarChart3,
    CheckCircle, ArrowRight, Github, BookOpen, Terminal,
    Target, Percent, Clock, Brain, Cpu, LineChart
} from 'lucide-react';

const LandingPage = () => {
    const [activeFaq, setActiveFaq] = useState(null);

    const features = [
        {
            icon: <Brain className="w-8 h-8" />,
            title: "Multi-Indicator Analysis",
            description: "14 technical indicators working together with intelligent weighted scoring for high-probability trades",
            color: "from-purple-500 to-pink-500"
        },
        {
            icon: <Target className="w-8 h-8" />,
            title: "Smart Risk Management",
            description: "ATR-based stop loss and take profit with 1:3 R/R ratio. Only needs 25% win rate to be profitable",
            color: "from-blue-500 to-cyan-500"
        },
        {
            icon: <Zap className="w-8 h-8" />,
            title: "Real-Time Signals",
            description: "WebSocket-powered live signal updates for both Spot and Futures markets across multiple timeframes",
            color: "from-yellow-500 to-orange-500"
        },
        {
            icon: <BarChart3 className="w-8 h-8" />,
            title: "Advanced Backtesting",
            description: "Test strategies on historical data with detailed metrics: ROI, win rate, profit factor, and more",
            color: "from-green-500 to-emerald-500"
        },
        {
            icon: <Shield className="w-8 h-8" />,
            title: "Paper Trading Mode",
            description: "Practice risk-free with simulated trading. Track performance before going live",
            color: "from-red-500 to-pink-500"
        },
        {
            icon: <Cpu className="w-8 h-8" />,
            title: "Auto-Trading Ready",
            description: "Automated execution with Binance integration. Set it and let it trade for you",
            color: "from-indigo-500 to-purple-500"
        }
    ];

    const stats = [
        { label: "Win Rate", value: "30.77%", icon: <Percent className="w-5 h-5" /> },
        { label: " ROI", value: "+0.74%", icon: <TrendingUp className="w-5 h-5" /> },
        { label: "Profit Factor", value: "1.26x", icon: <LineChart className="w-5 h-5" /> },
        { label: "Coins Scanned", value: "1000+", icon: <Activity className="w-5 h-5" /> }
    ];

    const timeframes = [
        { tf: "15m", use: "Scalping", confirmation: "Requires 1h" },
        { tf: "1h", use: "Intraday", confirmation: "Requires 4h" },
        { tf: "4h", use: "Swing Trading", confirmation: "None" },
        { tf: "1d", use: "Position Trading", confirmation: "None" }
    ];

    const faqs = [
        {
            q: "How does the signal generation work?",
            a: "The bot uses 14 technical indicators with weighted scoring. Each signal must pass pre-filters (ADX ≥ 18, volume spike, multi-timeframe alignment) and achieve minimum 73% confidence before being generated."
        },
        {
            q: "What is the trading strategy?",
            a: "RSI-based mean reversion with trend confirmation. LONG signals trigger when RSI is 23-33 (oversold), SHORT when 67-77 (overbought), with additional confirmation from MACD, SuperTrend, EMA alignment, and 12 other indicators."
        },
        {
            q: "How is risk managed?",
            a: "All signals include ATR-based stop loss (3.0x ATR) and take profit (9.0x ATR) for a 1:3 risk/reward ratio. This means you only need a 25% win rate to break even, making the strategy profitable long-term."
        },
        {
            q: "Can I backtest strategies?",
            a: "Yes! The built-in backtesting engine lets you test on historical data with configurable parameters. View detailed metrics including equity curve, trade history, drawdown, and performance by timeframe."
        },
        {
            q: "Do I need coding knowledge?",
            a: "No! The web interface handles everything. Just connect your Binance API (read-only for signals), configure parameters, and start receiving signals. Paper trading mode lets you practice first."
        },
        {
            q: "Which markets are supported?",
            a: "Both Binance Spot and Futures (USDT perpetual contracts with up to 10x leverage). The bot scans 1000+ trading pairs across 4 timeframes (15m, 1h, 4h, 1d)."
        }
    ];

    return (
        <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 text-white">
            {/* Hero Section */}
            <div className="relative overflow-hidden">
                {/* Animated Background */}
                <div className="absolute inset-0 opacity-30">
                    <div className="absolute top-0 left-1/4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl animate-blob"></div>
                    <div className="absolute top-0 right-1/4 w-96 h-96 bg-yellow-500 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-2000"></div>
                    <div className="absolute bottom-0 left-1/3 w-96 h-96 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-4000"></div>
                </div>

                {/* Navigation */}
                <nav className="relative z-10 container mx-auto px-6 py-6">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                            <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                                <TrendingUp className="w-6 h-6" />
                            </div>
                            <span className="text-2xl font-bold">RevX Bot</span>
                        </div>
                        <div className="hidden md:flex items-center space-x-8">
                            <a href="#features" className="hover:text-purple-400 transition-colors">Features</a>
                            <a href="#how-it-works" className="hover:text-purple-400 transition-colors">How It Works</a>
                            <a href="#performance" className="hover:text-purple-400 transition-colors">Performance</a>
                            <a href="#faq" className="hover:text-purple-400 transition-colors">FAQ</a>
                            <Link to="/login" className="px-6 py-2 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg hover:shadow-lg hover:shadow-purple-500/50 transition-all duration-300">
                                Get Started
                            </Link>
                        </div>
                    </div>
                </nav>

                {/* Hero Content */}
                <div className="relative z-10 container mx-auto px-6 py-20 md:py-32">
                    <div className="max-w-4xl mx-auto text-center">
                        <div className="inline-block mb-6 px-4 py-2 bg-purple-500/20 rounded-full border border-purple-500/30 backdrop-blur-sm">
                            <span className="text-purple-300 text-sm font-medium">🚀 Powered by 14 Technical Indicators</span>
                        </div>

                        <h1 className="text-5xl md:text-7xl font-bold mb-6 bg-gradient-to-r from-white via-purple-200 to-pink-200 bg-clip-text text-transparent">
                            AI-Powered Crypto Trading Signals
                        </h1>

                        <p className="text-xl md:text-2xl text-gray-300 mb-10 max-w-3xl mx-auto">
                            Professional-grade trading bot that scans 1000+ coins in real-time using RSI mean reversion with multi-indicator confirmation. <span className="text-purple-400 font-semibold">30.77% win rate</span> • <span className="text-green-400 font-semibold">1:3 R/R</span>
                        </p>

                        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
                            <Link to="/register" className="group px-8 py-4 bg-gradient-to-r from-purple-500 to-pink-500 rounded-xl font-semibold text-lg hover:shadow-2xl hover:shadow-purple-500/50 transition-all duration-300 flex items-center gap-2">
                                Start Free Trial
                                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                            </Link>
                            <a href="#how-it-works" className="px-8 py-4 bg-white/10 backdrop-blur-sm rounded-xl font-semibold text-lg border border-white/20 hover:bg-white/20 transition-all duration-300 flex items-center gap-2">
                                <BookOpen className="w-5 h-5" />
                                Learn More
                            </a>
                        </div>

                        {/* Stats */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
                            {stats.map((stat, idx) => (
                                <div key={idx} className="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10 hover:border-purple-500/50 transition-all duration-300">
                                    <div className="flex items-center justify-center mb-2 text-purple-400">
                                        {stat.icon}
                                    </div>
                                    <div className="text-3xl font-bold mb-1">{stat.value}</div>
                                    <div className="text-sm text-gray-400">{stat.label}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Features Section */}
            <div id="features" className="py-20 bg-gray-900/50">
                <div className="container mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">Powerful Features</h2>
                        <p className="text-xl text-gray-400">Everything you need for successful crypto trading</p>
                    </div>

                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
                        {features.map((feature, idx) => (
                            <div key={idx} className="group relative bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-white/10 hover:border-purple-500/50 transition-all duration-300 hover:-translate-y-2">
                                <div className={`inline-flex p-4 rounded-xl bg-gradient-to-br ${feature.color} mb-6 group-hover:scale-110 transition-transform duration-300`}>
                                    {feature.icon}
                                </div>
                                <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
                                <p className="text-gray-400">{feature.description}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* How It Works */}
            <div id="how-it-works" className="py-20">
                <div className="container mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">How It Works</h2>
                        <p className="text-xl text-gray-400">Three simple steps to start trading smarter</p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto">
                        <div className="text-center">
                            <div className="w-20 h-20 bg-gradient-to-br from-purple-500 to-pink-500 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl font-bold">
                                1
                            </div>
                            <h3 className="text-2xl font-bold mb-4">Connect API</h3>
                            <p className="text-gray-400">Link your Binance account with read-only API keys. Your funds stay safe in your exchange.</p>
                        </div>

                        <div className="text-center">
                            <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl font-bold">
                                2
                            </div>
                            <h3 className="text-2xl font-bold mb-4">Configure Strategy</h3>
                            <p className="text-gray-400">Choose timeframe (15m-1d), set confidence threshold, and customize risk parameters.</p>
                        </div>

                        <div className="text-center">
                            <div className="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl font-bold">
                                3
                            </div>
                            <h3 className="text-2xl font-bold mb-4">Receive Signals</h3>
                            <p className="text-gray-400">Get real-time alerts with entry, stop loss, take profit, and confidence score.</p>
                        </div>
                    </div>

                    {/* Timeframes */}
                    <div className="mt-20 max-w-4xl mx-auto">
                        <h3 className="text-3xl font-bold text-center mb-10">Supported Timeframes</h3>
                        <div className="grid md:grid-cols-4 gap-4">
                            {timeframes.map((tf, idx) => (
                                <div key={idx} className="bg-white/5 backdrop-blur-sm rounded-xl p-6 border border-white/10 hover:border-purple-500/50 transition-all">
                                    <div className="text-4xl font-bold text-purple-400 mb-2">{tf.tf}</div>
                                    <div className="text-sm text-gray-300 mb-2">{tf.use}</div>
                                    <div className="text-xs text-gray-500">{tf.confirmation}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* Performance Section */}
            <div id="performance" className="py-20 bg-gray-900/50">
                <div className="container mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">Proven Performance</h2>
                        <p className="text-xl text-gray-400">Based on 11 months of backtesting</p>
                    </div>

                    <div className="max-w-4xl mx-auto bg-gradient-to-br from-purple-900/30 to-pink-900/30 rounded-2xl p-8 md:p-12 border border-purple-500/30 backdrop-blur-sm">
                        <div className="grid md:grid-cols-2 gap-8 mb-8">
                            <div>
                                <div className="flex items-center gap-3 mb-4">
                                    <CheckCircle className="w-6 h-6 text-green-400" />
                                    <span className="text-2xl font-bold">Win Rate: 30.77%</span>
                                </div>
                                <p className="text-gray-400 ml-9">Nearly DOUBLED from previous 16.7%</p>
                            </div>

                            <div>
                                <div className="flex items-center gap-3 mb-4">
                                    <CheckCircle className="w-6 h-6 text-green-400" />
                                    <span className="text-2xl font-bold">ROI: +0.74%</span>
                                </div>
                                <p className="text-gray-400 ml-9">Improved from -0.03% (now profitable)</p>
                            </div>

                            <div>
                                <div className="flex items-center gap-3 mb-4">
                                    <CheckCircle className="w-6 h-6 text-green-400" />
                                    <span className="text-2xl font-bold">Profit Factor: 1.26x</span>
                                </div>
                                <p className="text-gray-400 ml-9">Above 1.0 means profitable system</p>
                            </div>

                            <div>
                                <div className="flex items-center gap-3 mb-4">
                                    <CheckCircle className="w-6 h-6 text-green-400" />
                                    <span className="text-2xl font-bold">52 Trades</span>
                                </div>
                                <p className="text-gray-400 ml-9">Sufficient sample size for validation</p>
                            </div>
                        </div>

                        <div className="bg-white/5 rounded-xl p-6 border border-white/10">
                            <div className="flex items-start gap-3">
                                <Target className="w-6 h-6 text-purple-400 mt-1" />
                                <div>
                                    <h4 className="text-xl font-bold mb-2">Why It Works</h4>
                                    <p className="text-gray-300">
                                        With 1:3 risk/reward ratio, you only need <span className="text-purple-400 font-semibold">25% win rate to break even</span>.
                                        At 30.77% win rate, the strategy is <span className="text-green-400 font-semibold">consistently profitable</span>.
                                        Wider stops (3.0x ATR) prevent premature stop-outs while larger targets (9.0x ATR) capture trend moves.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* FAQ Section */}
            <div id="faq" className="py-20">
                <div className="container mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">Frequently Asked Questions</h2>
                        <p className="text-xl text-gray-400">Everything you need to know</p>
                    </div>

                    <div className="max-w-3xl mx-auto space-y-4">
                        {faqs.map((faq, idx) => (
                            <div key={idx} className="bg-white/5 backdrop-blur-sm rounded-xl border border-white/10 overflow-hidden">
                                <button
                                    onClick={() => setActiveFaq(activeFaq === idx ? null : idx)}
                                    className="w-full p-6 text-left flex items-center justify-between hover:bg-white/5 transition-colors"
                                >
                                    <span className="text-xl font-semibold pr-8">{faq.q}</span>
                                    <ArrowRight className={`w-6 h-6 text-purple-400 transition-transform ${activeFaq === idx ? 'rotate-90' : ''}`} />
                                </button>
                                {activeFaq === idx && (
                                    <div className="px-6 pb-6 text-gray-400 leading-relaxed">
                                        {faq.a}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* CTA Section */}
            <div className="py-20 bg-gradient-to-r from-purple-900/50 to-pink-900/50">
                <div className="container mx-auto px-6 text-center">
                    <h2 className="text-4xl md:text-5xl font-bold mb-6">Ready to Start Trading Smarter?</h2>
                    <p className="text-xl text-gray-300 mb-10 max-w-2xl mx-auto">
                        Join traders using RevX Bot to identify high-probability setups with professional-grade analysis
                    </p>
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link to="/register" className="px-10 py-5 bg-gradient-to-r from-purple-500 to-pink-500 rounded-xl font-bold text-lg hover:shadow-2xl hover:shadow-purple-500/50 transition-all duration-300">
                            Create Free Account
                        </Link>
                        <Link to="/login" className="px-10 py-5 bg-white/10 backdrop-blur-sm rounded-xl font-bold text-lg border border-white/20 hover:bg-white/20 transition-all duration-300">
                            Sign In
                        </Link>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <footer className="py-12 bg-gray-900 border-t border-white/10">
                <div className="container mx-auto px-6">
                    <div className="flex flex-col md:flex-row items-center justify-between">
                        <div className="flex items-center space-x-2 mb-4 md:mb-0">
                            <div className="w-8 h-8 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
                                <TrendingUp className="w-5 h-5" />
                            </div>
                            <span className="text-xl font-bold">RevX Bot</span>
                        </div>
                        <div className="flex items-center space-x-6 text-gray-400">
                            <a href="https://github.com" className="hover:text-purple-400 transition-colors flex items-center gap-2">
                                <Github className="w-5 h-5" />
                                GitHub
                            </a>
                            <a href="#" className="hover:text-purple-400 transition-colors flex items-center gap-2">
                                <BookOpen className="w-5 h-5" />
                                Docs
                            </a>
                            <a href="#" className="hover:text-purple-400 transition-colors flex items-center gap-2">
                                <Terminal className="w-5 h-5" />
                                API
                            </a>
                        </div>
                    </div>
                    <div className="mt-8 text-center text-gray-500 text-sm">
                        © 2024 RevX Bot. All rights reserved. • Trading involves risk. Past performance does not guarantee future results.
                    </div>
                </div>
            </footer>

            <style>{`
        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
        </div>
    );
};

export default LandingPage;
