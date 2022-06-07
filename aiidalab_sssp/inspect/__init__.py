# -*- coding: utf-8 -*-
import random
from pathlib import Path

import matplotlib.pyplot as plt

DB_FOLDER = Path.home().joinpath(".cache", "SSSP")
SSSP_DB = Path.joinpath(DB_FOLDER, "sssp_db")

_px = 1 / plt.rcParams["figure.dpi"]  # unit pixel for plot


def extract_element(pseudos):
    try:
        # Since the element are same for all, use first one
        label0 = list(pseudos.keys())[0]
        element = label0.split(".")[0]
    except Exception:
        element = None

    return element


def get_conf_list(element):
    """get configuration list from element"""
    from aiida_sssp_workflow.utils import (
        OXIDE_CONFIGURATIONS,
        RARE_EARTH_ELEMENTS,
        UNARIE_CONFIGURATIONS,
    )

    if element == "O":
        return UNARIE_CONFIGURATIONS + ["TYPICAL"]

    if element in RARE_EARTH_ELEMENTS:
        return OXIDE_CONFIGURATIONS + ["RE"]

    return OXIDE_CONFIGURATIONS + UNARIE_CONFIGURATIONS + ["TYPICAL"]


def parse_label(label):
    """parse label to dict of pseudo info"""
    element, type, z, tool, family, *version = label.split(".")
    version = ".".join(version)

    if type == "nc":
        full_type = "NC"
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
        "representive_label": f"{z}|{full_type}|{family}|{tool}|{version}",
        "concise_label": f"{z}|{type}|{family}|{version}",
    }


def lighten_color(color, amount=0.5):
    """
    Lightens the given color by multiplying (1-luminosity) by the given amount.
    Input can be matplotlib color string, hex string, or RGB tuple.
    REF from https://stackoverflow.com/questions/37765197/darken-or-lighten-a-color-in-matplotlib

    Examples:
    >> lighten_color('g', 0.3)
    >> lighten_color('#F034A3', 0.6)
    >> lighten_color((.3,.55,.1), 0.5)
    """
    import colorsys

    import matplotlib.colors as mc

    try:
        c = mc.cnames[color]
    except Exception:
        c = color
    c = colorsys.rgb_to_hls(*mc.to_rgb(c))
    return colorsys.hls_to_rgb(c[0], 1 - amount * (1 - c[1]), c[2])


def cmap(pseudo_info: dict) -> str:
    """Return RGB string of color for given pseudo info
    Hardcoded at the momment.
    """
    if pseudo_info["family"] == "sg15" and pseudo_info["version"] == "v0":
        return "#000000"

    if pseudo_info["family"] == "gbrv":
        return "#4682B4"

    if (
        pseudo_info["family"] == "psl"
        and pseudo_info["type"] == "us"
        and pseudo_info["version"] == "v1.0.0-high"
    ):
        return "#F50E02"

    if (
        pseudo_info["family"] == "psl"
        and pseudo_info["type"] == "us"
        and pseudo_info["version"] == "v1.0.0-low"
    ):
        return lighten_color("#F50E02")

    if (
        pseudo_info["family"] == "psl"
        and pseudo_info["type"] == "paw"
        and pseudo_info["version"] == "v1.0.0-high"
    ):
        return "#008B00"

    if (
        pseudo_info["family"] == "psl"
        and pseudo_info["type"] == "paw"
        and pseudo_info["version"] == "v1.0.0-low"
    ):
        return lighten_color("#008B00")

    if (
        pseudo_info["family"] == "psl"
        and pseudo_info["type"] == "paw"
        and "v0." in pseudo_info["version"]
    ):
        return "#FF00FF"

    if (
        pseudo_info["family"] == "psl"
        and pseudo_info["type"] == "us"
        and "v0." in pseudo_info["version"]
    ):
        return lighten_color("#FF00FF")

    if pseudo_info["family"] == "dojo" and pseudo_info["version"] == "v4-str":
        return "#F9A501"

    if pseudo_info["family"] == "dojo" and pseudo_info["version"] == "v4-std":
        return lighten_color("#F9A501")

    if pseudo_info["family"] == "jth" and pseudo_info["version"] == "v1.1-str":
        return "#00C5ED"

    if pseudo_info["family"] == "jth" and pseudo_info["version"] == "v1.1-std":
        return lighten_color("#00C5ED")

    # TODO: more mapping
    # if a unknow type generate random color based on ascii sum
    ascn = sum([ord(c) for c in pseudo_info["representive_label"]])
    random.seed(ascn)
    return "#%06x" % random.randint(0, 0xFFFFFF)
