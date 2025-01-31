"""
Copyright 2022 ACCESS-NRI and contributors. See the top-level COPYRIGHT file for details.
SPDX-License-Identifier: Apache-2.0
"""

from typing import Any
import yaml
from pathlib import Path
from dataclasses import dataclass, field


with open(Path(__file__).parent / "config.yaml", "r") as f:
    config = yaml.safe_load(f)


@dataclass
class TelemetryRegister:
    endpoint: str
    items: set[str] = field(default_factory=set)


def build_endpoints(
    config: dict[str, Any], parent: str | None = None
) -> list[TelemetryRegister]:
    """
    Recursively join the keys of the dictionary until we reach a list
    Returns list of tuples (path, endpoint_list)
    """
    parent = parent or ""
    results = []

    for key, val in config.items():
        if isinstance(val, dict):
            # Recursively process dictionaries and extend results
            nested_results = build_endpoints(val, f"{parent}/{key}" if parent else key)
            results.extend(nested_results)
        elif isinstance(val, list):
            # Add tuple of (path, list) when we find a list
            full_path = "/".join([parent, key]) if parent else key
            results.append(TelemetryRegister(full_path, set(val)))

    return results


ENDPOINTS = {
    register.endpoint.replace("/", "_"): register.endpoint
    for register in build_endpoints(config)
}

REGISTRIES = {
    register.endpoint.replace("/", "_"): register.items
    for register in build_endpoints(config)
}
