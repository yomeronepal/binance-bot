from signals.models import TradingSession

# Clear any existing sessions to avoid duplicates
TradingSession.objects.all().delete()

# GW1: 17:00-18:00 NPT, Active Trading Window (all days)
TradingSession.objects.create(
    name='GW1',
    session_type='ACTIVE_TRADING_WINDOW',
    description='Golden Window 1: High win-rate period 17:00-18:00 NPT',
    start_hour=17,
    start_minute=0,
    end_hour=18,
    end_minute=0,
    active_days=[],  # All days
    active=True
)

# GW2: 21:00-23:00 NPT, Golden Window (Sun, Wed, Thu only)
# Python weekday: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
TradingSession.objects.create(
    name='GW2',
    session_type='GOLDEN_WINDOW',
    description='Golden Window 2: Premium window 21:00-23:00 NPT on Sunday, Wednesday, Thursday',
    start_hour=21,
    start_minute=0,
    end_hour=23,
    end_minute=0,
    active_days=[6, 2, 3],  # Sunday=6, Wednesday=2, Thursday=3
    active=True
)

# Window 2: 21:00-23:00 NPT, Active Trading Window (all days)
TradingSession.objects.create(
    name='Window 2',
    session_type='ACTIVE_TRADING_WINDOW',
    description='Active Trading Window 2: 21:00-23:00 NPT on all days',
    start_hour=21,
    start_minute=0,
    end_hour=23,
    end_minute=0,
    active_days=[],  # All days
    active=True
)

# Verify
print("\n✅ Seeded trading sessions:")
for session in TradingSession.objects.all():
    print(f"  - {session.name}: {session.start_hour:02d}:{session.start_minute:02d}-{session.end_hour:02d}:{session.end_minute:02d} {session.session_type}")
    if session.active_days:
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        days = ', '.join([day_names[d] for d in session.active_days])
        print(f"     Active days: {days}")

print(f"\nTotal sessions: {TradingSession.objects.count()}")
