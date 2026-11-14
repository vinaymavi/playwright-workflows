from prefect_gcp import GcpCredentials, GcsBucket

gcs_bucket = GcsBucket(
    bucket="contractor-automation-storage",
    gcp_credentials=GcpCredentials.load("gcp-cred"),
)
gcs_bucket.save("gcs-bucket")
