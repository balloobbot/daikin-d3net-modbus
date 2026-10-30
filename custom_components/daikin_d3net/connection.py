"""Transport parameters; Home Assistant owns the actual connection."""

from homeassistant.const import CONF_HOST, CONF_PORT
from modbus_connection import ModbusSerialParams, ModbusTcpParams

from .const import CONF_TRANSPORT, TRANSPORT_RTU


def connection_params(data) -> ModbusTcpParams | ModbusSerialParams:
    host = data[CONF_HOST].strip()
    port = data[CONF_PORT]
    if data[CONF_TRANSPORT] == TRANSPORT_RTU:
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return ModbusSerialParams(device=f"socket://{host}:{port}", baudrate=115200)
    return ModbusTcpParams(host=host, port=port)


def endpoint_id(data) -> str:
    """Identity when the adapter provides no hardware serial number."""
    return f"{data[CONF_HOST].strip().lower()}:{data[CONF_PORT]}:{data['unit_id']}"
