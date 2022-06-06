# -*- coding: utf-8 -*-
from pathlib import Path

DB_FOLDER = Path.home().joinpath(".cache", "SSSP")
SSSP_DB = Path.joinpath(DB_FOLDER, "sssp_db")


def parse_label(label):
    """parse label to dict of pseudo info"""
    element, type, z, tool, family, *version = label.split(".")
    version = ".".join(version)

    if type == "nc":
        full_type = "Norm-conserving"
    if type == "us":
        full_type = "Ultrasoft"
    if type == "paw":
        full_type = "PAW"

    return {
        "element": element,
        "type": type,
        "z": z,
        "tool": tool,
        "family": family,
        "version": version,
        "representive_label": f"{z}|{full_type}|{family}:{tool}:{version}",
    }
