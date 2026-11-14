import json
from pathlib import Path

from prefect_gcp import GcpCredentials

GCP_SERVICE_ACCOUNT_FILE_PATH = (
    "/Users/vinaymavi/gcp-service-accounts/contractor-automation.json"
)
with Path(GCP_SERVICE_ACCOUNT_FILE_PATH).open(encoding="utf-8") as credentials_file:
    service_account_info = json.load(credentials_file)

GcpCredentials(service_account_info=service_account_info).save("gcp-cred")
