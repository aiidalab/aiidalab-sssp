import random

import matplotlib.pyplot as plt
import numpy as np


def cmap(label: str) -> str:
    """Return RGB string of color for given standard psp label"""
    _, psp_type, psp_z, psp_family, psp_version = label.split("/")

    if psp_family == "sg15" and psp_version == "v1.2-o2":
        return "#000000"

    if psp_family == "sg15" and psp_version == "v1.2-o4":
        return "#708090"

    if psp_family == "gbrv" and psp_version == "v1":
        return "#4682B4"

    if psp_family == "psl" and psp_version == "v1.0.0" and psp_type == "us":
        return "#F50E02"

    if psp_family == "psl" and psp_version == "v1.0.0" and psp_type == "paw":
        return "#008B00"

    if psp_family == "psl" and psp_version == "v0.1" and psp_type == "paw":
        return "#FF00FF"

    if psp_family == "dojo" and psp_version == "v04":
        return "#F9A501"

    # TODO: more mapping
    # if a unknow type generate random color based on ascii sum
    ascn = sum([ord(c) for c in label])
    random.seed(ascn)
    return "#%06x" % random.randint(0, 0xFFFFFF)


def delta_measure_hist(pseudos: dict, measure_type):

    px = 1 / plt.rcParams["figure.dpi"]  # pixel in inches
    fig, ax = plt.subplots(1, 1, figsize=(1024 * px, 360 * px))
    configurations = [
        "BCC",
        "FCC",
        "SC",
        "Diamond",
        "XO",
        "X2O",
        "XO3",
        "X2O",
        "X2O3",
        "X2O5",
    ]
    num_configurations = len(configurations)

    # element
    try:
        # Since the element are same for all, use first one
        v0 = list(pseudos.values())[0]
        element = v0["pseudo_info"]["element"]
    except Exception:
        element = None

    if measure_type == "delta":
        keyname = "delta"
        ylabel = "Δ -factor"
    elif measure_type == "nu":
        keyname = "nu"
        ylabel = "ν -factor"

    for i, (label, output) in enumerate(pseudos.items()):
        idx = np.arange(num_configurations)  # the x locations for the groups
        width = 0.1  # the width of the bars

        y_delta = []
        for configuration in configurations:
            try:
                res = output["delta_measure"]["output_parameters"][f"{configuration}"]
                y_delta.append(res[keyname])
            except Exception:
                y_delta.append(-1)

        _, psp_type, psp_z, psp_family, psp_version = label.split("/")
        out_label = f"{psp_z}/{psp_type}({psp_family}-{psp_version})"

        ax.bar(
            idx + width * i,
            y_delta,
            width,
            color=cmap(label),
            edgecolor="black",
            linewidth=1,
            label=out_label,
        )
        ax.legend()
        ax.set_title(f"X={element}")

    ax.axhline(y=1.0, linestyle="--", color="gray")
    ax.set_ylabel(ylabel)
    ax.set_ylim([0, 10])
    ax.set_yticks(np.arange(10))
    ax.set_xticks(list(range(num_configurations)))
    ax.set_xticklabels(configurations)

    return fig


def convergence(pseudos: dict, wf_name, measure_name, ylabel, threshold=None):

    px = 1 / plt.rcParams["figure.dpi"]
    fig, (ax1, ax2) = plt.subplots(
        1, 2, gridspec_kw={"width_ratios": [2, 1]}, figsize=(1024 * px, 360 * px)
    )

    for label, output in pseudos.items():
        # Calculate the avg delta measure value
        structures = ["X", "XO", "X2O", "XO3", "X2O", "X2O3", "X2O5"]
        lst = []
        for structure in structures:
            try:
                res = output["delta_measure"]["output_delta_analyze"][
                    f"output_{structure}"
                ]
                lst.append(res["rel_errors_vec_length"])
            except Exception:
                pass

        avg_delta = sum(lst) / len(lst)

        try:
            res = output[wf_name]
            x_wfc = res["output_parameters_wfc_test"]["ecutwfc"]
            y_wfc = res["output_parameters_wfc_test"][measure_name]

            x_rho = res["output_parameters_rho_test"]["ecutrho"]
            y_rho = res["output_parameters_rho_test"][measure_name]

            wfc_cutoff = res["final_output_parameters"]["wfc_cutoff"]

            _, pp_family, pp_z, pp_type, pp_version = label.split("/")
            out_label = f"{pp_z}/{pp_type}(ν={avg_delta:.2f})({pp_family}-{pp_version})"

            ax1.plot(x_wfc, y_wfc, marker="o", color=cmap(label), label=out_label)
            ax2.plot(
                x_rho,
                y_rho,
                marker="o",
                color=cmap(label),
                label=f"cutoff wfc = {wfc_cutoff} Ry",
            )
        except Exception:
            pass

    ax1.set_ylabel(ylabel)
    ax1.set_xlabel("Wavefuntion cutoff (Ry)")
    ax1.set_title(
        "Fixed rho cutoff at 200 * dual (dual=4 for NC and dual=8 for non-NC)"
    )

    # ax2.legend(loc='upper left', bbox_to_anchor=(1, 1.0))
    ax1.legend()

    ax2.set_xlabel("Charge density cudoff (Ry)")
    ax2.set_title("Convergence test at fixed wavefunction cutoff")
    ax2.legend()

    if threshold:
        ax1.axhline(y=threshold, color="r", linestyle="--")
        ax2.axhline(y=threshold, color="r", linestyle="--")

        ax1.set_ylim(-0.5 * threshold, 10 * threshold)
        ax2.set_ylim(-0.5 * threshold, 10 * threshold)

    plt.tight_layout()

    return fig
