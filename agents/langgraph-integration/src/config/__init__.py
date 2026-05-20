"""Runtime configuration (tenant registry, etc.)."""

from config.tenant_registry import (
    TenantAccessError,
    allowed_clusters,
    assert_tenant_cluster_access,
    list_tenants,
    load_tenant_registry,
)

__all__ = [
    "TenantAccessError",
    "allowed_clusters",
    "assert_tenant_cluster_access",
    "list_tenants",
    "load_tenant_registry",
]
