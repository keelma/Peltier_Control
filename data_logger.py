from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
import csv
import pandas as pd


class SensorDataWriter:
    """
    Handles writing:
    - Temperature sensor arrays -> measurement 'temperature'
    - TEC electrical data -> measurement 'tec'
    - Fan RPM -> measurement 'fan'
    """

    def __init__(
        self,
        influx_url: str,
        token: str,
        org: str,
        bucket: str,
        sensor_type: str,
        csv_file_path: str = None,
        labels: list[str] = None
    ):
        self.bucket = bucket
        self.sensor_type = sensor_type
        self.csv_file_path = csv_file_path
        self.labels = labels

        self.client = InfluxDBClient(url=influx_url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

        if self.csv_file_path and self.labels:
            self._init_csv()

    def _init_csv(self):
        """Write CSV header for temperature measurements only."""
        with open(self.csv_file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp"] + self.labels)

    def write_temperature(self, timestamp: pd.Timestamp, values: list[float]):
        """
        Write RTD temperature values to InfluxDB and optionally to CSV.
        """
        if not self.labels or len(self.labels) != len(values):
            raise ValueError(
                "Labels must be defined and match the length of the values list."
            )

        point = (
            Point("temperature")
            .tag("type", self.sensor_type)
            .time(timestamp)
        )

        for label, value in zip(self.labels, values):
            point.field(label, float(value) if value is not None else float("nan"))

        self.write_api.write(bucket=self.bucket, record=point)

        if self.csv_file_path:
            row = [timestamp.isoformat()] + values
            with open(self.csv_file_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)

    def write_tec(self, timestamp: pd.Timestamp, name: str, set_current: float, meas_current: float, meas_voltage_plus: float, meas_voltage_minus: float):
        """
        Write TEC electrical values to measurement 'tec'.
        Tags:
        - name (identifier of the TEC controller)
        Fields:
        - current
        - voltage
        """
        point = (
            Point("tec")
            .tag("name", name)
            .time(timestamp)
            .field("set_current", float(set_current))
            .field("meas_current", float(meas_current))
            .field("meas_voltage_plus", float(meas_voltage_plus))
            .field("meas_voltage_minus", float(meas_voltage_minus))
        )

        self.write_api.write(bucket=self.bucket, record=point)


    def write_rpm(self, timestamp: pd.Timestamp, name: str, set_rpm: float, meas_rpm: float):
        """
        Write fan RPM to measurement 'fan'.
        Tags:
        - name (identifier of the fan)
        Field:
        - rpm
        """
        point = (
            Point("fan")
            .tag("name", name)
            .time(timestamp)
            .field("rpm", float(meas_rpm))
            .field("set_rpm", float(set_rpm))
        )

        self.write_api.write(bucket=self.bucket, record=point)
