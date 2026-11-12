"""Trait for opaque dock version metadata."""

from typing import Any

from roborock.data import DockInfo, RoborockDockTypeCode
from roborock.device_features import RoborockDockFeatures
from roborock.devices.traits.v1 import common
from roborock.exceptions import RoborockParsingException
from roborock.roborock_typing import RoborockCommand


def _supports_dock_info(dock_features: RoborockDockFeatures) -> bool:
    """Limit discovery to the dock family with an observed response."""
    return dock_features.dock_type == RoborockDockTypeCode.f1_dock


class DockInfoConverter(common.V1TraitDataConverter):
    """Keep only version metadata and sanitize malformed response context."""

    def convert(self, response: common.V1ResponseData) -> DockInfo:
        """Parse one dock info object without retaining its serial number."""
        context: dict[str, Any] = {"response": "[REDACTED]", "response_type": type(response).__name__}
        if isinstance(response, list):
            context["response_length"] = len(response)
        try:
            if isinstance(response, list):
                if len(response) != 1:
                    raise ValueError("Expected exactly one dock info object")
                response = response[0]
            if not isinstance(response, dict):
                raise TypeError("Expected a dock info object")
            version = response.get("version")
            if version is not None and not isinstance(version, str):
                context["version_type"] = type(version).__name__
                raise TypeError("Expected a string or null dock version")
            return DockInfo(version=version)
        except (TypeError, ValueError) as err:
            # Raise directly so the common refresh wrapper cannot attach the raw response.
            raise RoborockParsingException(
                trait_name="DockInfoTrait",
                command=RoborockCommand.GET_DOCK_INFO,
                payload=context,
                inner_error=err,
            ) from err


class DockInfoTrait(DockInfo, common.V1TraitMixin):
    """Dock metadata populated only by an explicit refresh."""

    command = RoborockCommand.GET_DOCK_INFO
    converter = DockInfoConverter()
    requires_dock_features = _supports_dock_info
