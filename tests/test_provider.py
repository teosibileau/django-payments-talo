import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.test import RequestFactory
from payments import PaymentError, PaymentStatus, RedirectNeeded

from payments_talo import TaloProvider


TOKEN_RESPONSE = {
    "message": "ok",
    "error": False,
    "data": {"token": "TL-eyJhbGciOi"},
}

CREATE_PAYMENT_RESPONSE = {
    "message": "ok",
    "error": False,
    "data": {
        "id": "VAR-abc123-ORDER_1",
        "payment_status": "PENDING",
        "payment_url": "https://checkout.talo.com.ar/pay/abc123",
        "quotes": [{"cvu": "000123456", "alias": "talo.pay.test"}],
        "expiration_timestamp": "2026-03-16T00:00:00Z",
    },
}

GET_PAYMENT_SUCCESS = {
    "message": "ok",
    "error": False,
    "data": {"id": "VAR-abc123-ORDER_1", "payment_status": "SUCCESS"},
}

GET_PAYMENT_REJECTED = {
    "message": "ok",
    "error": False,
    "data": {"id": "VAR-abc123-ORDER_1", "payment_status": "REJECTED"},
}

GET_PAYMENT_PENDING = {
    "message": "ok",
    "error": False,
    "data": {"id": "VAR-abc123-ORDER_1", "payment_status": "PENDING"},
}

REFUND_RESPONSE = {
    "status": "ok",
    "code": 200,
    "data": {
        "refund_id": "ref123",
        "payment_id": "VAR-abc123-ORDER_1",
        "amount": "1500.00",
        "currency": "ARS",
        "status": "CREATED",
    },
}


def _mock_response(json_data, status_code=200, ok=True):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.status_code = status_code
    resp.ok = ok
    resp.text = json.dumps(json_data)
    resp.raise_for_status.return_value = None
    return resp


class TestGetForm:
    @patch("payments_talo.provider.requests.post")
    def test_creates_payment_and_redirects(self, mock_post, provider, mock_payment):
        mock_post.side_effect = [
            _mock_response(TOKEN_RESPONSE),
            _mock_response(CREATE_PAYMENT_RESPONSE),
        ]

        with pytest.raises(RedirectNeeded) as exc_info:
            provider.get_form(mock_payment)

        assert str(exc_info.value) == "https://checkout.talo.com.ar/pay/abc123"
        assert mock_payment.transaction_id == "VAR-abc123-ORDER_1"
        mock_payment.change_status.assert_called_once_with(PaymentStatus.WAITING)
        mock_payment.save.assert_called_once()

        # Verify create payment payload
        create_call = mock_post.call_args_list[1]
        payload = create_call[1]["json"]
        assert payload["user_id"] == "test-user-id"
        assert payload["price"]["amount"] == "1500.00"
        assert payload["price"]["currency"] == "ARS"
        assert payload["payment_options"] == ["transfer"]
        assert payload["external_id"] == "test-token-123"

    @patch("payments_talo.provider.requests.post")
    def test_api_error(self, mock_post, provider, mock_payment):
        mock_post.side_effect = [
            _mock_response(TOKEN_RESPONSE),
            _mock_response(
                {"error": True, "message": "Bad request"}, status_code=400, ok=False
            ),
        ]

        with pytest.raises(PaymentError):
            provider.get_form(mock_payment)


class TestProcessData:
    @patch("payments_talo.provider.requests.get")
    @patch("payments_talo.provider.requests.post")
    def test_webhook_success(self, mock_post, mock_get, provider, mock_payment):
        mock_post.return_value = _mock_response(TOKEN_RESPONSE)
        mock_get.return_value = _mock_response(GET_PAYMENT_SUCCESS)

        factory = RequestFactory()
        request = factory.post(
            "/process/",
            data=json.dumps(
                {"paymentId": "VAR-abc123-ORDER_1", "externalId": "test-token-123"}
            ),
            content_type="application/json",
        )

        response = provider.process_data(mock_payment, request)

        assert response.status_code == 200
        mock_payment.change_status.assert_called_once_with(PaymentStatus.CONFIRMED)
        mock_payment.save.assert_called_once()

    @patch("payments_talo.provider.requests.get")
    @patch("payments_talo.provider.requests.post")
    def test_webhook_rejected(self, mock_post, mock_get, provider, mock_payment):
        mock_post.return_value = _mock_response(TOKEN_RESPONSE)
        mock_get.return_value = _mock_response(GET_PAYMENT_REJECTED)

        factory = RequestFactory()
        request = factory.post(
            "/process/",
            data=json.dumps(
                {"paymentId": "VAR-abc123-ORDER_1", "externalId": "test-token-123"}
            ),
            content_type="application/json",
        )

        response = provider.process_data(mock_payment, request)

        assert response.status_code == 200
        mock_payment.change_status.assert_called_once_with(PaymentStatus.REJECTED)

    @patch("payments_talo.provider.requests.get")
    @patch("payments_talo.provider.requests.post")
    def test_webhook_pending(self, mock_post, mock_get, provider, mock_payment):
        mock_post.return_value = _mock_response(TOKEN_RESPONSE)
        mock_get.return_value = _mock_response(GET_PAYMENT_PENDING)

        factory = RequestFactory()
        request = factory.post(
            "/process/",
            data=json.dumps(
                {"paymentId": "VAR-abc123-ORDER_1", "externalId": "test-token-123"}
            ),
            content_type="application/json",
        )

        response = provider.process_data(mock_payment, request)

        assert response.status_code == 200
        mock_payment.change_status.assert_called_once_with(PaymentStatus.WAITING)


class TestRefund:
    @patch("payments_talo.provider.requests.post")
    def test_full_refund(self, mock_post, provider, mock_payment):
        mock_post.side_effect = [
            _mock_response(TOKEN_RESPONSE),
            _mock_response(REFUND_RESPONSE),
        ]
        mock_payment.transaction_id = "VAR-abc123-ORDER_1"

        result = provider.refund(mock_payment)

        assert result == Decimal("1500.00")
        mock_payment.change_status.assert_called_once_with(PaymentStatus.REFUNDED)

        refund_call = mock_post.call_args_list[1]
        payload = refund_call[1]["json"]
        assert payload["refund_type"] == "FULL"
        assert "amount" not in payload

    @patch("payments_talo.provider.requests.post")
    def test_partial_refund(self, mock_post, provider, mock_payment):
        mock_post.side_effect = [
            _mock_response(TOKEN_RESPONSE),
            _mock_response(REFUND_RESPONSE),
        ]
        mock_payment.transaction_id = "VAR-abc123-ORDER_1"

        result = provider.refund(mock_payment, amount=500)

        assert result == Decimal("500")

        refund_call = mock_post.call_args_list[1]
        payload = refund_call[1]["json"]
        assert payload["refund_type"] == "PARTIAL"
        assert payload["amount"] == "500.00"


class TestAccessToken:
    @patch("payments_talo.provider.requests.post")
    def test_get_access_token(self, mock_post, provider):
        mock_post.return_value = _mock_response(TOKEN_RESPONSE)

        token = provider._get_access_token()

        assert token == "TL-eyJhbGciOi"
        mock_post.assert_called_once_with(
            "https://sandbox-api.talo.com.ar/users/test-user-id/tokens",
            json={
                "client_id": "test-client-id",
                "client_secret": "test-client-secret",
            },
        )

    @patch("payments_talo.provider.requests.post")
    def test_token_caching(self, mock_post, provider):
        mock_post.return_value = _mock_response(TOKEN_RESPONSE)

        provider._get_access_token()
        provider._get_access_token()

        mock_post.assert_called_once()


class TestConfiguration:
    def test_sandbox_url(self):
        p = TaloProvider(
            client_id="id", client_secret="secret", user_id="uid", sandbox=True
        )
        assert p.base_url == "https://sandbox-api.talo.com.ar"

    def test_production_url(self):
        p = TaloProvider(
            client_id="id", client_secret="secret", user_id="uid", sandbox=False
        )
        assert p.base_url == "https://api.talo.com.ar"
