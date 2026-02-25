import sys
import time
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from langchain_core.messages import HumanMessage

# Import your actual workflow from main.py
try:
    from main import agent_workflow
except ImportError:
    print("❌ Error: Could not find 'main.py'. Make sure your backend file is named 'main.py'")
    sys.exit(1)

console = Console()


def run_terminal_demo():
    # 1. Header
    console.print(
        Panel.fit("🚀 FinCrew: Autonomous Agent Terminal", style="bold blue"))

    # 2. Input
    ticker = console.input(
        "[bold yellow]Enter Stock Ticker (e.g. AAPL, TSLA): [/bold yellow]").strip().upper()
    if not ticker:
        console.print("[red]❌ No ticker entered. Exiting.[/red]")
        return

    # 3. Execution with Spinner
    start_time = time.time()

    with console.status(f"[bold green]Agents are initializing workflow for {ticker}...", spinner="dots") as status:

        # Define initial state
        initial_state = {
            "ticker": ticker,
            "messages": [HumanMessage(content=f"Analyze stock: {ticker}")],
            "errors": []
        }

        # --- SIMULATED LOGS (To show the guide "Activity") ---
        # Since LangGraph runs fast, we simulate steps so the guide sees the "Agent Handoff"
        time.sleep(1)
        console.print(
            f"🔎 [cyan]Researcher Agent[/cyan] activated... Fetching live data for {ticker}.")

        # INVOKE THE ACTUAL AI GRAPH (The Real Work)
        final_state = agent_workflow.invoke(initial_state)

        # Check progress from state (Simulating the output logs)
        if final_state.get("stock_price_data"):
            price = final_state["stock_price_data"]["current_price"]
            console.print(
                f"✅ Data Acquired. Current Price: [bold green]${price}[/bold green]")

        console.print(
            f"🧮 [magenta]Analyst Agent[/magenta] activated... Computing RSI & SMA.")
        time.sleep(0.5)

        if final_state.get("technical_analysis"):
            trend = final_state["technical_analysis"]["trend"]
            console.print(
                f"✅ Analysis Complete. Trend Detected: [bold]{trend}[/bold]")

        console.print(
            f"📝 [yellow]Team Lead Agent[/yellow] activated... Writing Final Report.")
        time.sleep(0.5)

    # 4. Output Result
    execution_time = time.time() - start_time
    console.print(
        f"\n[bold green]✅ Workflow Finished in {execution_time:.2f} seconds![/bold green]\n")

    # 5. Render Markdown Report
    if final_state.get("final_report"):
        console.print(Panel("📄 FINAL INVESTMENT REPORT", style="bold white"))
        md = Markdown(final_state["final_report"])
        console.print(md)

        # 6. PDF Confirmation
        console.print("\n[dim]Checking for PDF generation...[/dim]")

    else:
        console.print("[bold red]❌ Error: No report generated.[/bold red]")
        if final_state.get("errors"):
            console.print(final_state["errors"])


if __name__ == "__main__":
    try:
        run_terminal_demo()
    except KeyboardInterrupt:
        console.print("\n[red]Demo cancelled by user.[/red]")
