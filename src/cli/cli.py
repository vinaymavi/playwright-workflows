import typer

app = typer.Typer()

from flow.flow_challan import flow_challan

WORKFLOWS: dict[str, str] = {}
WORKFLOWS["challan"] = "flow_challan"


@app.command()
def hello(name: str) -> None:
    print(f"Hello {name} from playwright-workflows!")


@app.command()
def workflow(name: str) -> None:
    if name in WORKFLOWS:
        print(f"Running workflow {WORKFLOWS[name]} from playwright-workflows!")
        if name == "challan":
            flow_challan()
    else:
        print(f"Workflow {name} not found in playwright-workflows!")


if __name__ == "__main__":
    app()
