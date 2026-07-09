# -*- coding: utf-8 -*-
"""Data models for telemetry payload verification."""

from pydantic import BaseModel, Field

class SensorReading(BaseModel):
    """Pydantic model for sensor readings sent over Zenoh."""
    sensor_id: str = Field(..., description="Unique identifier for the sensor")
    device: str = Field(..., description="Device identifier (e.g., machine1)")
    measurement: str = Field(..., description="Measurement type (e.g., temperature)")
    value: float = Field(..., description="Numeric value of the measurement")
    unit: str = Field(..., description="Unit of measurement (e.g., celsius)")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp string")
