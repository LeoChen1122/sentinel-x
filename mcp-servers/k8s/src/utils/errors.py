class KubernetesError(Exception):
    """Base class for Kubernetes client failures."""

    pass


class KubernetesConnectionError(KubernetesError):
    """Transport-level failure (timeout, refused, TLS, DNS, etc.)."""

    pass


class KubernetesApiError(KubernetesError):
    """Kubernetes API returned a non-success HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
