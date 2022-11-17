import unittest
import redis
import responses
import settings
from unittest import mock
from datetime import datetime
from sms_anti_fraud import mobizon_sms_service, SmsNotSentException

r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)


class MockModel:
    class MockManager:
        def get_not_send_sms_phone_numbers(self):
            return [1, 2, 3]

        def get_sms_limit_enable(self):
            return True

        def get_sms_limit_count_per_user(self):
            return 10

        def get_sms_limit_period_in_seconds(self):
            return 300

    objects = MockManager()


class TestMobizonSmsService(unittest.TestCase):
    @responses.activate
    @mock.patch('django.apps.apps.get_model')
    def test_send_message(self,
                          mock_model,
                          ):
        responses.add(responses.GET, f'{settings.MOBIZON_URL}?recipient=+77051234567&text=Hello, its test.&apiKey={settings.MOBIZON_KEY}&from=easytap',
                      json={'data': {"messageId": "123456"}}, status=200)

        mock_model.return_value = MockModel()

        result = mobizon_sms_service.send_message(
            recipient_phone="+77051234567",
            text="Hello, its test."
        )
        self.assertEqual(result.get('data').get('messageId'), "123456", "Message not send")

    @mock.patch('django.apps.apps.get_model')
    def test_send_message_error(self, mock_model):

        mock_model.return_value = MockModel()

        with self.assertRaises(SmsNotSentException):
            result = mobizon_sms_service.send_message(
                recipient_phone="+770522",
                text="Hello, its test."
            )

    @mock.patch('django.apps.apps.get_model')
    def test_check_limit_not_exists(self, mock_model):
        mock_model.return_value = MockModel()

        r.delete('keykey1')

        result = mobizon_sms_service.check_limit(counter_key="keykey1",
                                                 first_sms_period_at_key='keykey1_first_request_time')
        self.assertEqual(result, False)

    @mock.patch('django.apps.apps.get_model')
    def test_check_limit_with_gte_period(self, mock_model):
        mock_model.return_value = MockModel()

        r.set('keykey2', 50)
        test_first_request_time = '2022-11-11 17:00:00'
        r.set('keykey2_first_request_time', test_first_request_time)
        result = mobizon_sms_service.check_limit(counter_key="keykey2",
                                                 first_sms_period_at_key='keykey2_first_request_time')
        self.assertEqual(result, False)

    @mock.patch('django.apps.apps.get_model')
    def test_check_limit_with_lte_period(self, mock_model):
        mock_model.return_value = MockModel()

        r.set('keykey3', 50)
        test_first_request_time = datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S')
        r.set('keykey3_first_request_time', test_first_request_time)
        result = mobizon_sms_service.check_limit(counter_key="keykey3",
                                                 first_sms_period_at_key='keykey3_first_request_time')
        self.assertEqual(result, True)


if __name__ == '__main__':
    unittest.main()
