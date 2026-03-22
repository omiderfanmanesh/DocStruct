"""Shared pytest fixtures for TOC extraction tests."""

import pathlib
import sys

import pytest

ROOT_DIR = pathlib.Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DATA_DIR = ROOT_DIR / "data"
GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"


@pytest.fixture(scope="session")
def notice_md_path() -> pathlib.Path:
    return DATA_DIR / "Notice_of_competition_scholarship_accommodation_and_degree_award_a.y.2025.26 (1).md"


@pytest.fixture(scope="session")
def disco_md_path() -> pathlib.Path:
    return DATA_DIR / "Bando_Borse_di_studio_2025-2026_ENG.md"


@pytest.fixture(scope="session")
def bologna_md_path() -> pathlib.Path:
    return DATA_DIR / "Bando di Concorso a.a. 2025.26_ENG_0.md"


@pytest.fixture(scope="session")
def all_md_paths(notice_md_path, disco_md_path, bologna_md_path):
    return [notice_md_path, disco_md_path, bologna_md_path]
