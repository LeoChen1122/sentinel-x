class PrometheusError(Exception):
    """Base class for Prometheus client failures."""

    pass


class PrometheusConnectionError(PrometheusError):
    """Transport-level failure (timeout, refused, TLS, DNS, etc.)."""

    pass


class PrometheusQueryError(PrometheusError):
    """Prometheus returned HTTP 200 with ``status`` ``error`` (invalid PromQL, etc.)."""

    pass
