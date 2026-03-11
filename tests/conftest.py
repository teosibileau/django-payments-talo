from decimal import Decimal
from unittest.mock import MagicMock

import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DATABASES={},
        PAYMENT_HOST="example.com",
        PAYMENT_USES_SSL=False,
    )
    django.setup()

import pytest

from payments_talo import TaloProvider


@pytest.fixture()
def provider():
    return TaloProvider(
        client_id="test-client-id",
        client_secret="test-client-secret",
        user_id="test-user-id",
        sandbox=True,
    )


@pytest.fixture()
def mock_payment():
    payment = MagicMock()
    payment.token = "test-token-123"
    payment.total = Decimal("1500.00")
    payment.currency = "ARS"
    payment.description = "Test payment"
    payment.transaction_id = None
    payment.status = "waiting"
    payment.attrs = {}
    payment.get_process_url.return_value = "https://example.com/process/"
    payment.get_success_url.return_value = "https://example.com/success/"
    payment.get_failure_url.return_value = "https://example.com/failure/"
    return payment
