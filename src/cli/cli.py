import typer
from flow.flow_challan import flow_challan

app = typer.Typer()

WORKFLOWS: dict[str, str] = {}
WORKFLOWS["challan"] = "flow_challan"


@app.command()
def hello(name: str) -> None:
    print(f"Hello {name} from playwright-workflows!")


@app.command()
def workflow(
    name: str,
    department: str = typer.Option(None, prompt="Department (exact dropdown label)"),
    division: str = typer.Option(None, prompt="Division (exact dropdown label)"),
    treasury: str = typer.Option(None, prompt="Treasury (exact dropdown label)"),
    depositor_name: str = typer.Option(None, prompt="Depositor name"),
    amount: str = typer.Option(None, prompt="Amount for second head"),
    block_no: str = "",
    locality: str = "",
    city: str = "",
    remarks: str = "",
) -> None:
    if name in WORKFLOWS:
        print(f"Running workflow {WORKFLOWS[name]} from playwright-workflows!")
        if name == "challan":
            result_url = flow_challan(
                department=department,
                division=division,
                treasury=treasury,
                remarks=remarks,
                depositor_name=depositor_name,
                block_no=block_no,
                locality=locality,
                city=city,
                amount=amount,
            )
            print(f"UPI QR image saved to {result_url}")
    else:
        print(f"Workflow {name} not found in playwright-workflows!")


if __name__ == "__main__":
    app()
