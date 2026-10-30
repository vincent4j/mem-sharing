"""Synthetic installed machine for project-command tests; never an installer."""
from agm_core.layout import resolve_layout
from agm_core.registry import empty_registry, serialize_registry


def installed_registry():
    data = empty_registry()
    data["product"] = {
        "product_id": "agent-group-memory", "installation_id": "fixture-machine",
        "product_structure_version": 1, "product_code_version": "0.4.0",
        "source": {"url": "fixture://agm", "commit": "a" * 40, "tree_sha256": "b" * 64},
        "installation_status": "complete", "last_operation_id": "fixture-install",
    }
    return data


def seed_runtime(home):
    runtime = resolve_layout(home)
    runtime.var.mkdir(parents=True)
    runtime.registry.write_bytes(serialize_registry(installed_registry()))
    return runtime
