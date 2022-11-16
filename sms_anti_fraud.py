import requests
import redis

# from django.conf import settings
import settings
from django.apps import apps
from sentry_sdk import capture_message


r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)


class SmsNotSentException(Exception):
    pass


class MobizonSmsService:
    def send_message(self, recipient_phone, text):
        if not settings.SEND_SMS:
            return

        not_send_sms_phone_numbers = apps.get_model('hrm.AdminSettings').objects.get_not_send_sms_phone_numbers()

        if recipient_phone in not_send_sms_phone_numbers:
            return

        sms_limit_enable = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_enable()
        if sms_limit_enable:
            if self.check_limit(recipient_phone=recipient_phone):
                return

        url = f'{settings.MOBIZON_URL}?recipient={recipient_phone}&text={text}&apiKey={settings.MOBIZON_KEY}&from=easytap'
        got = requests.get(url)

        message_id = got.json().get('data', {}).get('messageId')
        if not message_id:
            capture_message(f'#sms-fail: {recipient_phone} {text} | {got.json()}')
            raise SmsNotSentException()

        if sms_limit_enable:
            self.rate_limit(recipient_phone=recipient_phone)
        return got.json()

    def check_limit(self, recipient_phone: str) -> bool:
        if r.get(recipient_phone):
            sms_limit_count_per_user = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_count_per_user()
            current_count = int(r.get(recipient_phone))
            if current_count >= sms_limit_count_per_user:
                return True
        return False

    def rate_limit(self, recipient_phone: str):
        if not r.get(recipient_phone):
            sms_limit_period_in_seconds = apps.get_model('hrm.AdminSettings').objects.get_sms_limit_period_in_seconds()
            r.set(recipient_phone, 1, ex=int(sms_limit_period_in_seconds))
        else:
            current_count = int(r.get(recipient_phone))
            expired_period_in_seconds = r.ttl(recipient_phone)
            r.set(recipient_phone, current_count + 1, ex=expired_period_in_seconds)


mobizon_sms_service = MobizonSmsService()
