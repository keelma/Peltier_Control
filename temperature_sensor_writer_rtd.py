from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime
import csv
import pandas as pd

class TemperatureSensorWriterRTD:
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
        """Write CSV header."""
        with open(self.csv_file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp"] + self.labels)

    def write(self, timestamp: pd.Timestamp, values: list[float]):
        """
        Write list of values (RTD sensor readings) to InfluxDB and optionally to CSV.
        """
        if not self.labels or len(self.labels) != len(values):
            raise ValueError("Labels must be defined and match the length of the values list.")

        # InfluxDB point
        point = Point("temperature").tag("type", self.sensor_type).time(timestamp)
        for label, value in zip(self.labels, values):
            point.field(label, float(value) if value is not None else float("nan"))

        self.write_api.write(bucket=self.bucket, record=point)

        # Optional: Write to CSV
        if self.csv_file_path:
            row = [timestamp.isoformat()] + values
            with open(self.csv_file_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)

    def close(self):
        self.client.close()
