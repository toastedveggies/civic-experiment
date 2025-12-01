"""CLI interface using typer."""

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from la_agendas.discovery import (
    discover_all_pdf_links,
    find_meeting_detail_links,
    parse_html,
)
from la_agendas.extract import extract_links
from la_agendas.fetch import Fetcher
from la_agendas.output import (
    write_all_links_csv,
    write_coverage_report,
    write_preview_csv,
    write_summary_csv,
    write_unlabeled_csv,
)
from la_agendas.pdf_download import download_pdfs
from la_agendas.pdf_parse import parse_pdfs

app = typer.Typer(help="LA County Agendas Scraper")
console = Console()


def setup_logging(debug: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, console=console)],
    )


@app.command()
def crawl(
    base_url: str = typer.Option(
        "https://ceo.lacounty.gov/agendas/",
        "--base-url",
        help="Base URL to scrape",
    ),
    only_agenda_pdfs: bool = typer.Option(
        False,
        "--only-agenda-pdfs",
        help="Filter to only PDFs with 'agenda' in name/text",
    ),
    exclude_cancellations: bool = typer.Option(
        False,
        "--exclude-cancellations",
        help="Exclude PDFs with 'cancel' in name/text",
    ),
    outdir: str = typer.Option(
        "previews",
        "--outdir",
        help="Output directory for CSVs",
    ),
    download_pdfs_flag: bool = typer.Option(
        False,
        "--download-pdfs",
        help="Download PDFs to disk",
    ),
    rate_limit: float = typer.Option(
        2.0,
        "--rate-limit",
        help="Requests per second",
    ),
    timeout: int = typer.Option(
        60,
        "--timeout",
        help="Request timeout in seconds",
    ),
    user_agent: Optional[str] = typer.Option(
        None,
        "--user-agent",
        help="Custom User-Agent string",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Don't download PDFs, still write CSVs",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging",
    ),
) -> None:
    """Crawl LA County agendas site and extract PDF links."""
    setup_logging(debug)
    logger = logging.getLogger(__name__)

    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    default_ua = "la-county-agendas-scraper/0.1.0"
    ua = user_agent or default_ua

    fetcher = Fetcher(
        base_url=base_url,
        timeout=timeout,
        user_agent=ua,
        rate_limit=rate_limit,
    )

    console.print(f"[bold]Fetching base URL:[/bold] {base_url}")
    try:
        html_content = fetcher.fetch_html(base_url)
    except Exception as e:
        console.print(f"[red]Error fetching base URL:[/red] {e}")
        sys.exit(1)

    # Global PDF sweep on base page
    console.print("[bold]Running global PDF sweep...[/bold]")
    all_global_links = discover_all_pdf_links(html_content, base_url)

    # Extract links from base page (main pipeline)
    console.print("[bold]Extracting PDF links (main pipeline)...[/bold]")
    all_records = extract_links(
        html_content,
        base_url,
        only_agenda_pdfs=only_agenda_pdfs,
        exclude_cancellations=exclude_cancellations,
    )

    # Find and fetch meeting detail pages
    console.print("[bold]Finding meeting detail pages...[/bold]")
    doc = parse_html(html_content)
    detail_urls = find_meeting_detail_links(doc, base_url)
    console.print(f"Found {len(detail_urls)} potential detail pages")

    for detail_url in detail_urls:
        try:
            console.print(f"  Fetching: {detail_url}")
            detail_html = fetcher.fetch_html(detail_url)
            # Global sweep on detail page
            detail_global_links = discover_all_pdf_links(detail_html, detail_url)
            all_global_links.extend(detail_global_links)
            # Main pipeline extraction on detail page
            detail_records = extract_links(
                detail_html,
                detail_url,
                only_agenda_pdfs=only_agenda_pdfs,
                exclude_cancellations=exclude_cancellations,
            )
            all_records.extend(detail_records)
        except Exception as e:
            logger.warning(f"Error fetching detail page {detail_url}: {e}")

    # Deduplicate global links by URL
    from la_agendas.util import dedupe_records

    # Deduplicate global links strictly by URL
    seen_global_urls = set()
    unique_global_links = []
    for link in all_global_links:
        url = link.get("url", "")
        if url and url not in seen_global_urls:
            seen_global_urls.add(url)
            unique_global_links.append(link)
    all_global_links = unique_global_links

    # Deduplicate main pipeline records
    all_records = dedupe_records(all_records)

    # Log statistics
    total_pdfs = len(all_records)
    unlabeled_count = sum(1 for r in all_records if r.get("group") == "(unlabeled)")
    console.print(f"[green]Total unique PDFs found:[/green] {total_pdfs}")
    console.print(f"[yellow]Unlabeled PDFs:[/yellow] {unlabeled_count}")

    if unlabeled_count > 0:
        sample_unlabeled = [
            r for r in all_records if r.get("group") == "(unlabeled)"
        ][:5]
        console.print("[yellow]Sample unlabeled links:[/yellow]")
        for r in sample_unlabeled:
            console.print(f"  - {r.get('link_text', '')[:60]}...")

    # Write CSVs
    console.print("[bold]Writing CSV outputs...[/bold]")
    write_all_links_csv(all_records, outdir_path)
    write_summary_csv(all_records, outdir_path)
    write_preview_csv(all_records, outdir_path)
    write_unlabeled_csv(all_records, outdir_path)

    # Write coverage report
    console.print("[bold]Generating coverage report...[/bold]")
    global_count, pipeline_count, missing_count = write_coverage_report(
        all_records, all_global_links, outdir_path
    )

    # Print coverage statistics (always, but more detailed with --debug)
    console.print(f"[green]Coverage:[/green] {pipeline_count} PDFs in pipeline, {global_count} in global sweep")
    if missing_count > 0:
        console.print(f"[yellow]Missing:[/yellow] {missing_count} PDFs found globally but not in pipeline")
        missing_file = outdir_path / "missing_from_pipeline.csv"
        console.print(f"[yellow]Missing PDFs written to:[/yellow] {missing_file}")
    else:
        console.print("[green]✓ Pipeline covers all global PDFs[/green]")

    if debug:
        console.print(f"[dim]Debug: Global sweep found {global_count} unique PDFs[/dim]")
        console.print(f"[dim]Debug: Main pipeline found {pipeline_count} unique PDFs[/dim]")
        console.print(f"[dim]Debug: Missing count: {missing_count}[/dim]")
        if missing_count > 0:
            missing_file = outdir_path / "missing_from_pipeline.csv"
            console.print(f"[dim]Debug: Missing CSV location: {missing_file}[/dim]")

    # Download PDFs if requested
    if download_pdfs_flag and not dry_run:
        console.print("[bold]Downloading PDFs...[/bold]")
        download_pdfs(all_records, outdir_path, fetcher)
    elif download_pdfs_flag and dry_run:
        console.print("[yellow]Dry run: skipping PDF downloads[/yellow]")

    console.print(f"[green]✓ Done! Outputs written to {outdir_path}[/green]")


@app.command()
def verify(
    outdir: str = typer.Option(
        "previews",
        "--outdir",
        help="Output directory to verify",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging",
    ),
) -> None:
    """Verify CSV outputs for quality issues."""
    setup_logging(debug)
    logger = logging.getLogger(__name__)

    outdir_path = Path(outdir)
    if not outdir_path.exists():
        console.print(f"[red]Error: {outdir_path} does not exist[/red]")
        sys.exit(1)

    import pandas as pd

    issues = []
    warnings = []

    # Check all_links_raw.csv
    all_links_file = outdir_path / "all_links_raw.csv"
    if not all_links_file.exists():
        issues.append(f"Missing {all_links_file}")
    else:
        try:
            df = pd.read_csv(all_links_file)
            if df.empty:
                issues.append(f"{all_links_file} is empty")
            else:
                # Check for duplicate (group, url) pairs
                duplicates = df.duplicated(subset=["group", "url"], keep=False)
                if duplicates.any():
                    n_dup = duplicates.sum()
                    issues.append(f"{all_links_file} has {n_dup} duplicate (group, url) pairs")

                # Check URLs are absolute
                non_absolute = df[~df["url"].str.startswith(("http://", "https://"))]
                if not non_absolute.empty:
                    issues.append(
                        f"{all_links_file} has {len(non_absolute)} non-absolute URLs"
                    )

                # Check all are PDFs
                non_pdf = df[~df["url"].str.lower().str.contains(".pdf", na=False)]
                if not non_pdf.empty:
                    warnings.append(
                        f"{all_links_file} has {len(non_pdf)} non-PDF URLs"
                    )

                # Check date parse coverage
                unknown_dates = df[df["date"] == "unknown_date"]
                if not unknown_dates.empty:
                    coverage = 1.0 - (len(unknown_dates) / len(df))
                    warnings.append(
                        f"Date parsing coverage: {coverage:.1%} ({len(unknown_dates)} unknown dates)"
                    )
        except Exception as e:
            issues.append(f"Error reading {all_links_file}: {e}")

    # Check summary_by_group.csv
    summary_file = outdir_path / "summary_by_group.csv"
    if not summary_file.exists():
        issues.append(f"Missing {summary_file}")
    else:
        try:
            df = pd.read_csv(summary_file)
            if df.empty:
                issues.append(f"{summary_file} is empty")
            else:
                zero_counts = df[df["n_links"] == 0]
                if not zero_counts.empty:
                    warnings.append(
                        f"{summary_file} has {len(zero_counts)} groups with zero links"
                    )
        except Exception as e:
            issues.append(f"Error reading {summary_file}: {e}")

    # Print results
    if issues:
        console.print("[red]Issues found:[/red]")
        for issue in issues:
            console.print(f"  ✗ {issue}")
    else:
        console.print("[green]✓ No critical issues found[/green]")

    if warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  ⚠ {warning}")

    if not issues and not warnings:
        console.print("[green]✓ All checks passed![/green]")

    sys.exit(1 if issues else 0)


@app.command(name="parse-pdfs")
def parse_pdfs_cmd(
    pdf_dir: str = typer.Option(
        "previews/pdfs",
        "--pdf-dir",
        help="Directory containing downloaded PDFs",
    ),
    outdir: str = typer.Option(
        "previews",
        "--outdir",
        help="Output directory for extracted text",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable debug logging",
    ),
) -> None:
    """Extract text from downloaded PDFs."""
    setup_logging(debug)
    pdf_dir_path = Path(pdf_dir)
    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)

    if not pdf_dir_path.exists():
        console.print(f"[red]Error: {pdf_dir_path} does not exist[/red]")
        sys.exit(1)

    console.print(f"[bold]Extracting text from PDFs in {pdf_dir_path}...[/bold]")
    parse_pdfs(pdf_dir_path, outdir_path)
    console.print(f"[green]✓ Done! Outputs written to {outdir_path}[/green]")


if __name__ == "__main__":
    app()

