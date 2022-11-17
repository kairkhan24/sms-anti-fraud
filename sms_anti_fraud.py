import requests
import redis

# from django.conf import settings
import settings
from django.apps import apps
from sentry_sdk import capture_message
from datetime import datetime


r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)


class SmsNotSentException(Exception):
    pass


class MobizonSmsService:
    SMS_SENT_IN_PERIOD_COUNTER_KEY = 'sms_limit_{phone}_counter'
    FIRST_SMS_SENT_IN_PERIOD_AT_KEY = 'sms_limit_{phone}_first_request_time'

    def as_counter_key(self, phone):
        return self.SMS_SENT_IN_PERIOD_COUNTER_KEY.format(phone=phone)

    def as_first_sms_period_key(self, phone):
        return self.FIRST_SMS_SENT_IN_PERIOD_AT_KEY.format(phone=phone)

    def send_message(self, recipient_phone, text):
        if not settings.SEND_SMS:
            return

        not_send_sms_phone_numbers = apps.get_model('hrm.AdminSettings').objects.get_not_send_sms_phone_numbers()

        if recipient_phone in not_send_sms_phone_numbers:
            return

        sms_limit_enable = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_enable()

        counter_key = self.as_counter_key(phone=recipient_phone)
        first_sms_period_at_key = self.as_first_sms_period_key(phone=recipient_phone)
        if sms_limit_enable:
            try:
                if self.check_limit(counter_key, first_sms_period_at_key):
                    return
            except Exception as e:
                capture_message(f'#sms-fail: {recipient_phone} {text} | check_limit | {str(e)}')
                raise SmsNotSentException(str(e))

        url = f'{settings.MOBIZON_URL}?recipient={recipient_phone}&text={text}&apiKey={settings.MOBIZON_KEY}&from=easytap'
        got = requests.get(url)

        message_id = got.json().get('data', {}).get('messageId')
        if not message_id:
            capture_message(f'#sms-fail: {recipient_phone} {text} | {got.json()}')
            raise SmsNotSentException()

        if sms_limit_enable:
            try:
                self.rate_limit(counter_key, first_sms_period_at_key)
            except Exception as e:
                capture_message(f'#sms-fail: {recipient_phone} {text} | rate_limit | {str(e)}')
                raise SmsNotSentException(str(e))
        return got.json()

    def check_limit(self, counter_key: str, first_sms_period_at_key: str) -> bool:
        if not r.get(counter_key):
            return False

        sms_limit_count_per_user = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_count_per_user()
        sms_limit_period_in_seconds = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_period_in_seconds()
        current_count = int(r.get(counter_key))

        first_request_time = r.get(first_sms_period_at_key).decode('utf-8')
        first_request_dt = datetime.strptime(first_request_time, '%Y-%m-%d %H:%M:%S')
        now_dt = datetime.now()

        diff_dt = now_dt - first_request_dt
        if diff_dt.total_seconds() >= sms_limit_period_in_seconds:
            r.delete(counter_key)
            r.delete(first_sms_period_at_key)
            return False

        return current_count >= sms_limit_count_per_user

    def rate_limit(self, counter_key: str, first_sms_period_at_key: str):
        if not r.get(counter_key):
            r.set(counter_key, 1)
            first_request_time = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
            r.set(first_sms_period_at_key, first_request_time)
        else:
            r.incr(counter_key)


mobizon_sms_service = MobizonSmsService()
