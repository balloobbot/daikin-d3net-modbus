"""Transport parameters; Home Assistant owns the actual connection."""

from urllib.parse import urlsplit

from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT
from modbus_connection import ModbusSerialParams, ModbusTcpParams

from .const import (
    CONF_BAUDRATE,
    CONF_PARITY,
    CONF_TRANSPORT,
    CONF_UNIT_ID,
    TRANSPORT_RTU_OVER_TCP,
    TRANSPORT_SERIAL,
)


def connection_params(data) -> ModbusTcpParams | ModbusSerialParams:
    if data[CONF_TRANSPORT] == TRANSPORT_SERIAL:
        parity = "N" if data[CONF_PARITY] == "n1" else data[CONF_PARITY].upper()
        return ModbusSerialParams(
            device=data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            parity=parity,
            stopbits=2 if parity == "N" and data[CONF_PARITY] != "n1" else 1,
        )
    host = data[CONF_HOST].strip()
    port = data[CONF_PORT]
    # Keep existing RTU-over-TCP entries working with their original settings.
    if data[CONF_TRANSPORT] == TRANSPORT_RTU_OVER_TCP:
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return ModbusSerialParams(device=f"socket://{host}:{port}", baudrate=115200)
    return ModbusTcpParams(host=host, port=port)


def endpoint_id(data) -> str:
    """Identity when the adapter provides no hardware serial number."""
    if data[CONF_TRANSPORT] == TRANSPORT_SERIAL:
        device = data[CONF_DEVICE]
        if device.startswith("socket://"):
            endpoint = urlsplit(device)
            # Detect duplicates of entries created by the old RTU-over-TCP flow.
            return f"{endpoint.hostname}:{endpoint.port}:{data[CONF_UNIT_ID]}"
        return f"serial:{device}:{data[CONF_UNIT_ID]}"
    return f"{data[CONF_HOST].strip().lower()}:{data[CONF_PORT]}:{data[CONF_UNIT_ID]}"
