import matplotlib.pyplot as plt

from aiidalab_sssp.inspect import cmap

CONFIGURATIONS = [
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


def convergence(pseudos: dict, wf_name, measure_name, ylabel, threshold=None):

    px = 1 / plt.rcParams["figure.dpi"]
    fig, (ax1, ax2) = plt.subplots(
        1, 2, gridspec_kw={"width_ratios": [2, 1]}, figsize=(960 * px, 360 * px)
    )

    for label, output in pseudos.items():
        # Calculate the avg delta measure value
        lst = []
        for configuration in CONFIGURATIONS:
            try:
                res = output["delta_measure"]["output_parameters"][f"{configuration}"]
                lst.append(res["nu"])
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

            _, pp_family, pp_z, pp_type, pp_version = label.split("/")[0:5]
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
            raise

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
