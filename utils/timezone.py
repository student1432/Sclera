"""
Timezone utilities for StudyOS
Handles user timezone detection and conversion
"""
import pytz
from datetime import datetime, timezone
from typing import Optional, Union


class TimezoneManager:
    """Manages timezone conversion for users"""

    @staticmethod
    def get_utc_now() -> datetime:
        """Get current UTC time as datetime object"""
        return datetime.now(timezone.utc)

    @staticmethod
    def get_utc_now_iso() -> str:
        """Get current UTC time as ISO string"""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def detect_user_timezone() -> str:
        """
        Detect user's timezone from browser/client
        For now, default to UTC+5:30 (IST) which is common in India
        In a full implementation, this would use JavaScript to detect client timezone
        """
        return 'Asia/Kolkata'  # Default to IST

    @staticmethod
    def get_user_timezone(user_data: dict) -> str:
        """Get user's timezone from profile, with fallback"""
        return user_data.get('timezone', 'Asia/Kolkata')  # Default to IST

    @staticmethod
    def utc_to_user_timezone(utc_datetime: Union[str, datetime], user_timezone: str) -> datetime:
        """
        Convert UTC datetime to user's timezone
        Args:
            utc_datetime: UTC datetime (string or datetime object)
            user_timezone: User's timezone string (e.g., 'Asia/Kolkata')
        Returns:
            Datetime in user's timezone
        """
        # Parse if it's a string
        if isinstance(utc_datetime, str):
            # Handle both ISO format and other formats
            try:
                utc_dt = datetime.fromisoformat(utc_datetime.replace('Z', '+00:00'))
            except ValueError:
                # Fallback for other formats
                utc_dt = datetime.strptime(utc_datetime, '%Y-%m-%d %H:%M:%S.%f')
            # Ensure it's UTC
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        else:
            utc_dt = utc_datetime

        # Convert to user's timezone
        try:
            user_tz = pytz.timezone(user_timezone)
            return utc_dt.astimezone(user_tz)
        except pytz.exceptions.UnknownTimeZoneError:
            # Fallback to UTC if invalid timezone
            return utc_dt

    @staticmethod
    def format_for_display(utc_datetime: Union[str, datetime], user_timezone: str, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        Convert UTC time to user's timezone and format for display
        Args:
            utc_datetime: UTC datetime (string or datetime object)
            user_timezone: User's timezone string
            format_str: Format string for output
        Returns:
            Formatted time string in user's timezone
        """
        user_dt = TimezoneManager.utc_to_user_timezone(utc_datetime, user_timezone)
        return user_dt.strftime(format_str)

    @staticmethod
    def get_current_user_time(user_timezone: str) -> datetime:
        """Get current time in user's timezone"""
        utc_now = TimezoneManager.get_utc_now()
        return TimezoneManager.utc_to_user_timezone(utc_now, user_timezone)

    @staticmethod
    def get_current_user_time_iso(user_timezone: str) -> str:
        """Get current time in user's timezone as ISO string"""
        user_now = TimezoneManager.get_current_user_time(user_timezone)
        return user_now.isoformat()


# Convenience functions for common operations
def get_user_timezone(user_data: dict) -> str:
    """Get user's timezone from profile"""
    return TimezoneManager.get_user_timezone(user_data)


def format_timestamp_for_user(utc_timestamp: str, user_data: dict) -> str:
    """Format UTC timestamp for user's timezone display"""
    user_tz = get_user_timezone(user_data)
    return TimezoneManager.format_for_display(utc_timestamp, user_tz)


def get_current_time_for_user(user_data: dict) -> str:
    """Get current time in user's timezone as ISO string"""
    user_tz = get_user_timezone(user_data)
    return TimezoneManager.get_current_user_time_iso(user_tz)
