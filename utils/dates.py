from datetime import datetime, timedelta

def get_next_race_date():
    today = datetime.today()
    days_until_tuesday = (1 - today.weekday()) % 7
    next_tuesday = today + timedelta(days=days_until_tuesday)
    return next_tuesday.strftime("%Y-%m-%d")