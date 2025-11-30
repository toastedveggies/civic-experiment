"""Tests for CLI functionality."""

import pytest
from typer.testing import CliRunner

from la_agendas.cli import app

runner = CliRunner()


def test_cli_help():
    """Test that CLI shows help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "LA County Agendas Scraper" in result.stdout


def test_cli_crawl_help():
    """Test that crawl command shows help."""
    result = runner.invoke(app, ["crawl", "--help"])
    assert result.exit_code == 0
    assert "Crawl LA County agendas site" in result.stdout


def test_cli_verify_help():
    """Test that verify command shows help."""
    result = runner.invoke(app, ["verify", "--help"])
    assert result.exit_code == 0
    assert "Verify CSV outputs" in result.stdout

