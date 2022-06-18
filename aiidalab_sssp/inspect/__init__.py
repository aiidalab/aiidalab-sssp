# -*- coding: utf-8 -*-
import json
import os
import random
from pathlib import Path

import matplotlib.pyplot as plt
from aiida import orm
from aiida.common import AttributeDict
from monty.json import jsanitize

DB_FOLDER = Path.home().joinpath(".cache", "SSSP")
SSSP_DB = Path.joinpath(DB_FOLDER, "sssp_db")
SSSP_LOCAL_DB = Path.joinpath(DB_FOLDER, "sssp_local_db")

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
        "full_label": f"{element}|{z}|{full_type}|{family}|{tool}|{version}",
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


def dump_to_sssp_local_db(node):
    """dump node to the local db
    - element summary
    - bands
    - band structure.
    """
    _node = node
    label = _node.extras.get("label").split()[
        -1
    ]  # do not contain the extra machine info
    element = label.split(".")[0]

    json_fn = f"{element}.json"
    Path(os.path.join(SSSP_LOCAL_DB, "bands", element)).mkdir(
        parents=True, exist_ok=True
    )
    Path(os.path.join(SSSP_LOCAL_DB, "band_structure", element)).mkdir(
        parents=True, exist_ok=True
    )

    assert f"{label}.upf" == _node.inputs.pseudo.filename

    res_json = os.path.join(SSSP_LOCAL_DB, json_fn)
    if os.path.exists(res_json):
        with open(res_json, "r") as fh:
            curated_result = json.load(fh)
    else:
        curated_result = {}  # all results of pseudos of the elements

    psp_result = {
        "_metadata": [get_metadata(_node)],
    }  # the results of one verification
    psp_result["accuracy"] = {}
    psp_result["convergence"] = {}

    for called_wf in _node.called:
        if called_wf.process_label == "parse_pseudo_info":
            psp_result["pseudo_info"] = {
                **called_wf.outputs.result.get_dict(),
            }
        # delta
        if called_wf.process_label == "DeltaMeasureWorkChain":
            psp_result["accuracy"]["delta"] = _flatten_output(
                _node.outputs.accuracy.delta
            )
            psp_result["accuracy"]["delta"]["_metadata"] = get_metadata(called_wf)
        # bands
        if called_wf.process_label == "BandsMeasureWorkChain":
            psp_result["accuracy"]["bands"] = {
                "bands": f"bands/{element}/{label}.json",
                "band_structure": f"band_structure/{element}/{label}.json",
            }
            psp_result["accuracy"]["bands"]["_metadata"] = get_metadata(called_wf)

            with open(
                os.path.join(SSSP_LOCAL_DB, "bands", element, f"{label}.json"), "w"
            ) as fh:
                bands = called_wf.outputs.bands
                json.dump(
                    export_bands_data(bands.band_structure, bands.band_parameters), fh
                )
            with open(
                os.path.join(SSSP_LOCAL_DB, "band_structure", element, f"{label}.json"),
                "w",
            ) as fh:
                bands = called_wf.outputs.band_structure
                json.dump(
                    export_bands_structure(bands.band_structure, bands.band_parameters),
                    fh,
                )

        # convergence
        for k, v in process_prop_label_mapping.items():
            if called_wf.process_label == v:
                try:
                    output_res = _flatten_output(_node.outputs.convergence[k])
                except KeyError:
                    # run but not finished therefore no output node
                    output_res = {"message": "error"}
                psp_result["convergence"][k] = output_res
                psp_result["convergence"][k]["_metadata"] = get_metadata(called_wf)

    curated_result[f"{label}"] = psp_result

    with open(os.path.join(SSSP_LOCAL_DB, json_fn), "w") as fh:
        json.dump(dict(curated_result), fh, indent=2, sort_keys=True, default=str)

    return psp_result


def get_metadata(node):
    return {
        "uuid": node.uuid,
        "ctime": node.ctime,
        "_aiida_hash": node.get_hash(),
    }


def export_bands_structure(band_structure, band_parameters):
    data = json.loads(band_structure._exportcontent("json", comments=False)[0])
    data["fermi_level"] = band_parameters["fermi_energy"]
    data["number_of_electrons"] = band_parameters["number_of_electrons"]
    data["number_of_bands"] = band_parameters["number_of_bands"]

    return jsanitize(data)


def export_bands_data(band_structure: orm.BandsData, band_parameters: orm.Dict):
    bands_arr = band_structure.get_bands()
    kpoints_arr, weights_arr = band_structure.get_kpoints(also_weights=True)

    data = {
        "fermi_level": band_parameters["fermi_energy"],
        "number_of_electrons": band_parameters["number_of_electrons"],
        "number_of_bands": band_parameters["number_of_bands"],
        "bands": bands_arr.tolist(),
        "kpoints": kpoints_arr.tolist(),  # TODO: using override JSON encoder
        "weights": weights_arr.tolist(),
    }

    return data


def _flatten_output(attr_dict, skip: list = lambda: []):
    """
    flaten output dict node
    node_collection is a list to accumulate the nodes that not unfolded

    :param skip: is a list of keys (format with parent_key.key) of Dict name that
        will not collected into the json file.

    For output nodes not being expanded, write down the uuid and datatype for future query.
    """
    # do_not_unfold = ["band_parameters", "scf_parameters", "seekpath_parameters"]

    for key, value in attr_dict.items():
        if key in skip:
            continue

        if isinstance(value, AttributeDict):
            # keep on unfold if it is a namespace
            _flatten_output(value, skip)
        elif isinstance(value, orm.Dict):
            attr_dict[key] = value.get_dict()
        elif isinstance(value, orm.Int):
            attr_dict[key] = value.value
        else:
            # node type not handled attach uuid
            attr_dict[key] = {
                "uuid": value.uuid,
                "datatype": type(value),
            }

    # print(archive_uuids)
    return attr_dict


process_prop_label_mapping = {
    "cohesive_energy": "ConvergenceCohesiveEnergyWorkChain",
    "phonon_frequencies": "ConvergencePhononFrequenciesWorkChain",
    "pressure": "ConvergencePressureWorkChain",
    "bands": "ConvergenceBandsWorkChain",
    "delta": "ConvergenceDeltaWorkChain",
}
