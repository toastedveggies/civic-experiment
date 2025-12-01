"""CSV output generation."""

import logging
from pathlib import Path
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)


def write_all_links_csv(records: List[dict], outdir: Path) -> None:
    """Write all_links_raw.csv with columns: group,date,link_text,url,filename."""
    df = pd.DataFrame(records)
    if df.empty:
        logger.warning("No records to write to all_links_raw.csv")
        return
    # Ensure columns exist
    columns = ["group", "date", "link_text", "url", "filename"]
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns]
    outfile = outdir / "all_links_raw.csv"
    df.to_csv(outfile, index=False)
    logger.info(f"Wrote {len(df)} records to {outfile}")


def write_summary_csv(records: List[dict], outdir: Path) -> None:
    """Write summary_by_group.csv with: group,n_links,min_date,max_date."""
    if not records:
        logger.warning("No records to write to summary_by_group.csv")
        return
    df = pd.DataFrame(records)
    if df.empty:
        return

    # Group by 'group' and aggregate
    summary = []
    for group, group_df in df.groupby("group"):
        dates = group_df["date"].tolist()
        # Filter out 'unknown_date'
        valid_dates = [d for d in dates if d != "unknown_date"]
        min_date = min(valid_dates) if valid_dates else "unknown_date"
        max_date = max(valid_dates) if valid_dates else "unknown_date"
        summary.append(
            {
                "group": group,
                "n_links": len(group_df),
                "min_date": min_date,
                "max_date": max_date,
            }
        )

    summary_df = pd.DataFrame(summary)
    summary_df = summary_df.sort_values("group")
    outfile = outdir / "summary_by_group.csv"
    summary_df.to_csv(outfile, index=False)
    logger.info(f"Wrote summary for {len(summary_df)} groups to {outfile}")


def write_preview_csv(records: List[dict], outdir: Path, top_n: int = 5) -> None:
    """Write preview_top5_by_group.csv with top N per group, sorted by date desc."""
    if not records:
        logger.warning("No records to write to preview_top5_by_group.csv")
        return
    df = pd.DataFrame(records)
    if df.empty:
        return

    # Sort: group asc, date desc (unknown_date last), link_text asc
    df_sorted = df.copy()
    # Create a sortable date column (unknown_date -> 9999-99-99 for sorting)
    df_sorted["_date_for_sort"] = df_sorted["date"].replace("unknown_date", "9999-99-99")
    df_sorted = df_sorted.sort_values(
        by=["group", "_date_for_sort", "link_text"],
        ascending=[True, False, True],  # group asc, date desc, link_text asc
    )
    df_sorted = df_sorted.drop(columns=["_date_for_sort"])

    # Take top N per group
    preview = []
    for group, group_df in df_sorted.groupby("group"):
        top = group_df.head(top_n)
        preview.append(top)

    if preview:
        preview_df = pd.concat(preview, ignore_index=True)
        columns = ["group", "date", "link_text", "url"]
        for col in columns:
            if col not in preview_df.columns:
                preview_df[col] = ""
        preview_df = preview_df[columns]
        outfile = outdir / "preview_top5_by_group.csv"
        preview_df.to_csv(outfile, index=False)
        logger.info(f"Wrote preview with {len(preview_df)} records to {outfile}")


def write_unlabeled_csv(records: List[dict], outdir: Path) -> None:
    """Write unlabeled_links.csv for manual review."""
    unlabeled = [r for r in records if r.get("group") == "(unlabeled)"]
    if not unlabeled:
        logger.info("No unlabeled links to write")
        return
    df = pd.DataFrame(unlabeled)
    columns = ["group", "date", "link_text", "url", "filename"]
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    df = df[columns]
    outfile = outdir / "unlabeled_links.csv"
    df.to_csv(outfile, index=False)
    logger.info(f"Wrote {len(df)} unlabeled links to {outfile}")


def write_coverage_report(
    pipeline_records: List[dict], global_links: List[dict], outdir: Path
) -> tuple[int, int, int]:
    """
    Write coverage report CSVs comparing global sweep vs main pipeline.
    Returns (global_count, pipeline_count, missing_count).
    """
    # Write all_pdf_links_global.csv
    if global_links:
        global_df = pd.DataFrame(global_links)
        # Ensure columns exist
        columns = ["link_text", "url", "filename"]
        for col in columns:
            if col not in global_df.columns:
                global_df[col] = ""
        global_df = global_df[columns]
        global_file = outdir / "all_pdf_links_global.csv"
        global_df.to_csv(global_file, index=False)
        logger.info(f"Wrote {len(global_df)} global PDF links to {global_file}")
    else:
        logger.warning("No global PDF links to write")
        global_df = pd.DataFrame(columns=["link_text", "url", "filename"])

    # Find missing PDFs (in global but not in pipeline)
    if not pipeline_records:
        # If pipeline found nothing, all global links are missing
        if not global_df.empty:
            missing_df = global_df.copy()
            missing_df["group"] = "(unknown)"
            missing_df["date"] = "(unknown)"
        else:
            missing_df = pd.DataFrame(columns=["group", "date", "link_text", "url", "filename"])
    else:
        pipeline_df = pd.DataFrame(pipeline_records)
        # Get URLs from pipeline
        pipeline_urls = set(pipeline_df["url"].tolist() if "url" in pipeline_df.columns else [])

        # Find global links not in pipeline
        missing = []
        for link in global_links:
            url = link.get("url", "")
            if url and url not in pipeline_urls:
                missing.append(
                    {
                        "group": "(unknown)",
                        "date": "(unknown)",
                        "link_text": link.get("link_text", ""),
                        "url": url,
                        "filename": link.get("filename", ""),
                    }
                )

        missing_df = pd.DataFrame(missing)

    # Write missing_from_pipeline.csv
    if not missing_df.empty:
        columns = ["group", "date", "link_text", "url", "filename"]
        for col in columns:
            if col not in missing_df.columns:
                missing_df[col] = ""
        missing_df = missing_df[columns]
        missing_file = outdir / "missing_from_pipeline.csv"
        missing_df.to_csv(missing_file, index=False)
        logger.info(f"Wrote {len(missing_df)} missing PDF links to {missing_file}")
    else:
        logger.info("No missing PDFs found - pipeline covers all global links")
        # Still write empty file for consistency
        missing_df = pd.DataFrame(columns=["group", "date", "link_text", "url", "filename"])
        missing_file = outdir / "missing_from_pipeline.csv"
        missing_df.to_csv(missing_file, index=False)

    global_count = len(global_df)
    pipeline_count = len(pipeline_records)
    missing_count = len(missing_df)

    return (global_count, pipeline_count, missing_count)

