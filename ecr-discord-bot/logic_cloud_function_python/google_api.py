import os
import sys
from typing import Any

from google.api_core.extended_operation import ExtendedOperation
from google.cloud import compute_v1


# ---GOOGLE_APPLICATION_CREDENTIALS---
# It is required for the login to work to have set the GOOGLE_APPLICATION_CREDENTIALS environnement variable
# It must be the path towards the json file containing the service account key


class GoogleWorker:
    def __init__(self):
        self.google_project_id = os.getenv("GOOGLE_PROJECT_ID", "")
        if not self.google_project_id:
            raise ValueError("GOOGLE_PROJECT_ID not set")

        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""):
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not set")

    @staticmethod
    def wait_for_extended_operation(
            operation: ExtendedOperation, verbose_name: str = "operation", timeout: int = 300
    ) -> Any:
        result = operation.result(timeout=timeout)
        if operation.error_code:
            print(
                f"Error during {verbose_name}: [Code: {operation.error_code}]: {operation.error_message}",
                file=sys.stderr,
                flush=True,
            )
            print(f"Operation ID: {operation.name}", file=sys.stderr, flush=True)
            raise operation.exception() or RuntimeError(operation.error_message)

        if operation.warnings:
            print(f"Warnings during {verbose_name}:\n", file=sys.stderr, flush=True)
            for warning in operation.warnings:
                print(f" - {warning.code}: {warning.message}", file=sys.stderr, flush=True)

        return result

    def start_instance(self, region: str, instance_name: str) -> Any:
        instance_client = compute_v1.InstancesClient()

        operation = instance_client.start(
            project=self.google_project_id, zone=region, instance=instance_name
        )

        return self.wait_for_extended_operation(operation, "instance start")

    def stop_instance(self, region: str, instance_name: str) -> Any:
        instance_client = compute_v1.InstancesClient()

        operation = instance_client.stop(
            project=self.google_project_id, zone=region, instance=instance_name
        )

        return self.wait_for_extended_operation(operation, "instance stopping")


if __name__ == '__main__':
    gw = GoogleWorker()
    instance_data = {"zone": "us-central1-a", "name": "instance-1"}
    r = gw.start_instance(instance_data["zone"], instance_data["name"])
    print(r)
