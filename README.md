# django-payments-talo

A [django-payments](https://github.com/jazzband/django-payments) backend for [Talo](https://talo.com.ar/), an Argentine payment platform for bank transfers.

## Features

- Bank transfer payments via Talo
- Webhook handling for async status updates
- Full and partial refunds
- Sandbox environment support

## Requirements

- Python >= 3.12
- Django < 5.3
- django-payments >= 3.1.0, < 4.0.0

## Installation

```bash
pip install django-payments-talo
```

Or with Poetry:

```bash
poetry add django-payments-talo
```

## Configuration

Add Talo to your `PAYMENT_VARIANTS` setting:

```python
PAYMENT_VARIANTS = {
    "talo": (
        "payments_talo.TaloProvider",
        {
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
            "user_id": "your-user-id",
            "sandbox": True,  # Set to False for production
        },
    ),
}
```

| Parameter | Description |
|---|---|
| `client_id` | Talo API client ID |
| `client_secret` | Talo API client secret |
| `user_id` | Talo user ID |
| `sandbox` | `True` for sandbox, `False` (default) for production |

## Status Mapping

Talo payment statuses are mapped to django-payments statuses as follows:

| Talo Status | django-payments Status |
|---|---|
| `PENDING` | `waiting` |
| `SUCCESS` | `confirmed` |
| `REJECTED` | `rejected` |
| `CANCELLED` | `rejected` |
| `EXPIRED` | `rejected` |
| `UNDER_REVIEW` | `waiting` |
| `OVERPAID` | `confirmed` |
| `UNDERPAID` | `waiting` |

## Unsupported Operations

`capture` and `release` raise `NotImplementedError` — bank transfers do not have an authorization/capture flow.

## Development

```bash
poetry install
poetry run pytest
```

## License

MIT
