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
    REDIS_KEY_PREFIX = 'sms_limit_'

    def send_message(self, recipient_phone, text):

        if not settings.SEND_SMS:
            return

        not_send_sms_phone_numbers = apps.get_model('hrm.AdminSettings').objects.get_not_send_sms_phone_numbers()

        if recipient_phone in not_send_sms_phone_numbers:
            return

        sms_limit_enable = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_enable()

        r_key = f'{self.REDIS_KEY_PREFIX}{recipient_phone}'
        if sms_limit_enable:
            if self.check_limit(r_key=r_key):
                return

        url = f'{settings.MOBIZON_URL}?recipient={recipient_phone}&text={text}&apiKey={settings.MOBIZON_KEY}&from=easytap'
        got = requests.get(url)

        message_id = got.json().get('data', {}).get('messageId')
        if not message_id:
            capture_message(f'#sms-fail: {recipient_phone} {text} | {got.json()}')
            raise SmsNotSentException()

        if sms_limit_enable:
            self.rate_limit(r_key=r_key)
        return got.json()

    def check_limit(self, r_key: str) -> bool:
        if r.get(r_key):
            sms_limit_count_per_user = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_count_per_user()
            sms_limit_period_in_seconds = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_period_in_seconds()
            current_count = int(r.get(r_key))

            first_request_time = r.get(f'{r_key}_first_request_time').decode('utf-8')
            first_request_dt = datetime.strptime(first_request_time, '%Y-%m-%d %H:%M:%S')
            now_dt = datetime.now()

            diff_dt = now_dt - first_request_dt
            if diff_dt.total_seconds() >= sms_limit_period_in_seconds:
                r.delete(r_key)
                r.delete(f'{r_key}_first_request_time')
                return False

            if current_count >= sms_limit_count_per_user:
                return True
        return False

    def rate_limit(self, r_key: str):
        if not r.get(r_key):
            r.set(r_key, 1)
            first_request_time = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
            r.set(f'{r_key}_first_request_time', first_request_time)
        else:
            r.incr(r_key)


mobizon_sms_service = MobizonSmsService()
