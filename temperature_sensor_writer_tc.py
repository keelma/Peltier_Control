from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import csv
import pandas as pd

class TemperatureSensorWriterTC:
    def __init__(
        self,
        influx_url: str,
        token: str,
        org: str,
        bucket: str,
        csv_file_path: str = None,
        label_map: dict[str, tuple[str, str]] = None
    ):
        self.bucket = bucket
        self.csv_file_path = csv_file_path
        self.label_map = label_map  # { original_label: (location_tag, field_name) }

        self.client = InfluxDBClient(url=influx_url, token=token, org=org)
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)

        if self.csv_file_path and self.label_map:
            self._init_csv()

    def _init_csv(self):
        with open(self.csv_file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp"] + list(self.label_map.keys()))

    def write(self, timestamp: pd.Timestamp, values: list[float]):
        if not self.label_map or len(values) != len(self.label_map):
            raise ValueError("Label map must be defined and match length of values.")

        for label, value in zip(self.label_map.keys(), values):
            location_tag, field_name = self.label_map[label]
            point = (
                Point("peltier")
                .tag("location", location_tag)
                .field(field_name, float(value) if value is not None else float("nan"))
                .time(timestamp)
            )
            self.write_api.write(bucket=self.bucket, record=point)

        if self.csv_file_path:
            row = [timestamp.isoformat()] + values
            with open(self.csv_file_path, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(row)

    def close(self):
        self.client.close()
