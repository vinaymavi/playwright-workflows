from prefect import flow


@flow(log_prints=True)
def flow_challan():
    print("Running flow_challan")
