import unittest
import responses
import settings
from unittest import mock
from sms_anti_fraud import mobizon_sms_service


class TestMobizonSmsService(unittest.TestCase):
    @responses.activate
    @mock.patch('django.apps.apps.get_model')
    def test_send_message(self,
                          # mock_requests,
                          mock_model,
                          ):
        responses.add(responses.GET, f'{settings.MOBIZON_URL}?recipient=+77051234567&text=Hello, its test.&apiKey={settings.MOBIZON_KEY}&from=easytap',
                      json={'data': {"messageId": "123456"}}, status=200)

        mock_model.objects.get_not_send_sms_phone_numbers.return_value = [1, 2, 3]
        mock_model.objects.get_sms_limit_enable.return_value = True
        mock_model.objects.get_sms_limit_count_per_user.return_value = 10
        mock_model.objects.get_sms_limit_period_in_seconds.return_value = 120

        result = mobizon_sms_service.send_message(
            recipient_phone="+77051234567",
            text="Hello, its test."
        )
        self.assertEqual(result.get('data').get('messageId'), "123456", "Message not send")


if __name__ == '__main__':
    unittest.main()
