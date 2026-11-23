"""Trait for information reported by the dock."""

from roborock.data import DockInfo
from roborock.device_features import RoborockDockFeatures
from roborock.devices.traits.v1 import common
from roborock.exceptions import RoborockParsingException
from roborock.roborock_typing import RoborockCommand


def _supports_dock_info(dock_features: RoborockDockFeatures) -> bool:
    return dock_features.is_dock_info_supported


def _parsing_error(response: common.V1ResponseData, reason: str) -> RoborockParsingException:
    # The response carries the dock serial (`sn`), so only its type goes into the error.
    return RoborockParsingException(
        trait_name="DockInfoTrait",
        command=RoborockCommand.GET_DOCK_INFO,
        payload=f"<redacted {type(response).__name__}>",
        inner_error=reason,
    )


class DockInfoConverter(common.V1TraitDataConverter):
    """Reads only the scalar `version` from a `get_dock_info` response."""

    def convert(self, response: common.V1ResponseData) -> DockInfo:
        """Parse the response, raising errors that never include the response values."""
        data = response[0] if isinstance(response, list) and len(response) == 1 else response
        if not isinstance(data, dict):
            raise _parsing_error(response, "expected a dict or a one-item list containing a dict")
        version = data.get("version")
        if version is None or version == "None":
            return DockInfo()
        if isinstance(version, bool) or not isinstance(version, str | int):
            raise _parsing_error(response, f"unexpected version type {type(version).__name__}")
        return DockInfo(version=str(version))


class DockInfoTrait(DockInfo, common.V1TraitMixin):
    """Trait for information reported by the dock, such as its version."""

    command = RoborockCommand.GET_DOCK_INFO
    converter = DockInfoConverter()
    requires_dock_features = _supports_dock_info
