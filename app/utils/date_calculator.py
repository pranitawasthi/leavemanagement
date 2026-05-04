from datetime import date, timedelta
from typing import Iterable, Optional, Set


def calculate_leave_days(
    start_date: date,
    end_date: date,
    holidays: Optional[Iterable[date]] = None,
    include_weekends: bool = False,
) -> float:
    if end_date < start_date:
        raise ValueError("end_date cannot be before start_date")

    holiday_set: Set[date] = set(holidays or [])
    current_date = start_date
    leave_days = 0

    while current_date <= end_date:
        is_weekend = current_date.weekday() >= 5
        is_holiday = current_date in holiday_set

        if (include_weekends or not is_weekend) and not is_holiday:
            leave_days += 1

        current_date += timedelta(days=1)

    return float(leave_days)
