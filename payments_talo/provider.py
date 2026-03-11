from decimal import Decimal

import requests
from django.http import HttpResponse
from payments import PaymentError, PaymentStatus, RedirectNeeded
from payments.core import BasicProvider
import json


TALO_STATUS_MAP = {
    "PENDING": PaymentStatus.WAITING,
    "SUCCESS": PaymentStatus.CONFIRMED,
    "REJECTED": PaymentStatus.REJECTED,
    "CANCELLED": PaymentStatus.REJECTED,
    "EXPIRED": PaymentStatus.REJECTED,
    "UNDER_REVIEW": PaymentStatus.WAITING,
    "OVERPAID": PaymentStatus.CONFIRMED,
    "UNDERPAID": PaymentStatus.WAITING,
}


class TaloProvider(BasicProvider):
    def __init__(self, client_id, client_secret, user_id, sandbox=False, **kwargs):
        super().__init__(**kwargs)
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_id = user_id
        if sandbox:
            self.base_url = "https://sandbox-api.talo.com.ar"
        else:
            self.base_url = "https://api.talo.com.ar"
        self._token = None

    def _get_access_token(self):
        if self._token is not None:
            return self._token
        data = self._post(
            f"/users/{self.user_id}/tokens",
            {"client_id": self.client_id, "client_secret": self.client_secret},
            add_headers=False,
        )
        self._token = data["data"]["token"]
        return self._token

    def _headers(self):
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer TL-{token}",
            "Content-Type": "application/json",
        }

    def _post(self, path, payload, add_headers=True):
        headers = self._headers() if add_headers else {}
        response = requests.post(
            f"{self.base_url}{path}", json=payload, headers=headers
        )
        if not response.ok:
            raise PaymentError(
                f"Talo API error: {response.status_code} {response.text}"
            )
        return response.json()

    def _get(self, path):
        response = requests.get(f"{self.base_url}{path}", headers=self._headers())
        if not response.ok:
            raise PaymentError(
                f"Talo API error: {response.status_code} {response.text}"
            )
        return response.json()

    def get_form(self, payment, data=None):
        result = self._post(
            "/payments/",
            {
                "user_id": self.user_id,
                "price": {
                    "amount": str(payment.total),
                    "currency": payment.currency,
                },
                "payment_options": ["transfer"],
                "external_id": payment.token,
                "webhook_url": payment.get_process_url(),
                "redirect_url": payment.get_success_url(),
            },
        )
        payment_data = result["data"]
        payment.transaction_id = payment_data["id"]
        payment.attrs = result
        payment.change_status(PaymentStatus.WAITING)
        payment.save()
        raise RedirectNeeded(payment_data["payment_url"])

    def process_data(self, payment, request):
        body = json.loads(request.body)
        payment_id = body["paymentId"]
        result = self._get(f"/payments/{payment_id}")
        talo_status = result["data"]["payment_status"]
        django_status = TALO_STATUS_MAP.get(talo_status, PaymentStatus.WAITING)
        payment.change_status(django_status)
        payment.save()
        return HttpResponse(status=200)

    def refund(self, payment, amount=None):
        if amount is None or Decimal(str(amount)) == payment.total:
            refund_type = "FULL"
            payload = {"refund_type": refund_type}
        else:
            refund_type = "PARTIAL"
            payload = {
                "refund_type": refund_type,
                "amount": f"{Decimal(str(amount)):.2f}",
            }
        self._post(f"/payments/{payment.transaction_id}/refunds", payload)
        payment.change_status(PaymentStatus.REFUNDED)
        payment.save()
        return Decimal(str(amount)) if amount else payment.total

    def capture(self, payment, amount=None):
        raise NotImplementedError("Talo does not support capture (bank transfers only)")

    def release(self, payment):
        raise NotImplementedError("Talo does not support release (bank transfers only)")
