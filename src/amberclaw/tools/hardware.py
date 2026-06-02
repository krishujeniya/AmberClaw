\"\"\"
Hardware and Edge Integration Tools for AmberClaw AI OS
\"\"\"
import asyncio
from typing import Any, Optional
from pydantic import BaseModel, Field

# Graceful imports for optional dependencies
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

try:
    import gpiozero
except ImportError:
    gpiozero = None

from .registry import BaseTool


class SerialWriteSchema(BaseModel):
    port: str = Field(..., description="Serial port name (e.g., /dev/ttyUSB0 or COM3)")
    baudrate: int = Field(9600, description="Baud rate for serial communication")
    message: str = Field(..., description="The message/command to send to the microcontroller")


class SerialReadSchema(BaseModel):
    port: str = Field(..., description="Serial port name")
    baudrate: int = Field(9600, description="Baud rate")
    timeout: float = Field(2.0, description="Timeout in seconds for reading")


class GPIOWriteSchema(BaseModel):
    pin: int = Field(..., description="GPIO pin number (BCM)")
    value: int = Field(..., description="Value to set (0 for LOW, 1 for HIGH)")


class HardwareControlTool(BaseTool):
    \"\"\"Tool to send commands to microcontrollers (Arduino/ESP) via Serial.\"\"\"
    name = "hardware_send_command"
    description = "Sends a string command to an external microcontroller via Serial (Arduino/ESP/etc.)"
    args_schema = SerialWriteSchema

    async def run(self, port: str, baudrate: int, message: str) -> str:
        if not serial:
            return "Error: 'pyserial' is not installed. Run 'pip install pyserial' to use this tool."
        
        try:
            # Run in executor since serial calls are blocking
            loop = asyncio.get_event_loop()
            def _write():
                with serial.Serial(port, baudrate, timeout=1) as ser:
                    ser.write(message.encode('utf-8'))
                    return f"Sent command '{message}' to {port}"
            
            return await loop.run_in_executor(None, _write)
        except Exception as e:
            return f"Hardware Error: {str(e)}"


class HardwareReadTool(BaseTool):
    \"\"\"Tool to read sensor data from microcontrollers via Serial.\"\"\"
    name = "hardware_read_sensor"
    description = "Reads a line of data from an external sensor/microcontroller via Serial"
    args_schema = SerialReadSchema

    async def run(self, port: str, baudrate: int, timeout: float = 2.0) -> str:
        if not serial:
            return "Error: 'pyserial' is not installed."
        
        try:
            loop = asyncio.get_event_loop()
            def _read():
                with serial.Serial(port, baudrate, timeout=timeout) as ser:
                    line = ser.readline().decode('utf-8').strip()
                    return f"Data received: {line}" if line else "No data received within timeout."
            
            return await loop.run_in_executor(None, _read)
        except Exception as e:
            return f"Hardware Error: {str(e)}"


class GPIOTool(BaseTool):
    \"\"\"Tool to control Raspberry Pi GPIO pins directly.\"\"\"
    name = "rpi_gpio_control"
    description = "Controls Raspberry Pi GPIO pins (set HIGH/LOW). Requires running on an RPi."
    args_schema = GPIOWriteSchema

    async def run(self, pin: int, value: int) -> str:
        if not gpiozero:
            return "Error: 'gpiozero' is not installed or not running on a compatible ARM system."
        
        try:
            # We use OutputDevice for generic control
            from gpiozero import OutputDevice
            device = OutputDevice(pin)
            if value == 1:
                device.on()
                status = "HIGH"
            else:
                device.off()
                status = "LOW"
            return f"GPIO Pin {pin} set to {status}"
        except Exception as e:
            return f"GPIO Error: {str(e)}"


class HardwareScanTool(BaseTool):
    \"\"\"Tool to list available hardware ports.\"\"\"
    name = "hardware_list_ports"
    description = "Lists all available Serial ports (USB/UART) on the current system."

    async def run(self) -> str:
        if not serial:
            return "Error: 'pyserial' is not installed."
        
        ports = serial.tools.list_ports.comports()
        if not ports:
            return "No serial devices found."
        
        port_list = [f"{p.device} - {p.description}" for p in ports]
        return "Available Ports:\n" + "\n".join(port_list)
