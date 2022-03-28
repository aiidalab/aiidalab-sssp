import ipywidgets as ipw
import pandas as pd
import traitlets
from IPython.display import clear_output, display

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


class SummaryWidget(ipw.VBox):
    """output the convergence summary"""

    selected_pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        # Delta mesure
        self.output = ipw.Output()

        super().__init__(
            children=[
                self.output,
            ],
        )

    @traitlets.observe("selected_pseudos")
    def _on_pseudos_change(self, change):
        if change["new"]:
            with self.output:
                clear_output(wait=True)

                display(pd_summary_table(change["new"]))


def pd_summary_table(pseudos: dict):

    rows = []
    for label, output in pseudos.items():
        try:
            lst = []
            for configuration in CONFIGURATIONS:
                try:
                    res = output["delta_measure"]["output_parameters"][
                        f"{configuration}"
                    ]
                    lst.append(res["nu"])
                except Exception:
                    pass

            avg_delta = sum(lst) / len(lst)

            cohesive_energy = output["convergence_cohesive_energy"][
                "final_output_parameters"
            ]
            phonon_frequencies = output["convergence_phonon_frequencies"][
                "final_output_parameters"
            ]
            pressure = output["convergence_pressure"]["final_output_parameters"]
            bands = output["convergence_bands"]["final_output_parameters"]
            delta = output["convergence_delta"]["final_output_parameters"]

            rows.append(
                [
                    label,
                    (cohesive_energy["wfc_cutoff"], cohesive_energy["rho_cutoff"]),
                    (
                        phonon_frequencies["wfc_cutoff"],
                        phonon_frequencies["rho_cutoff"],
                    ),
                    (pressure["wfc_cutoff"], pressure["rho_cutoff"]),
                    (delta["wfc_cutoff"], delta["rho_cutoff"]),
                    (bands["wfc_cutoff"], bands["rho_cutoff"]),
                    avg_delta,
                ]
            )

        except Exception as e:
            raise e

    return pd.DataFrame(
        rows,
        columns=[
            "label",
            "cohesive energy",
            "phonon frequencies",
            "pressure",
            "delta",
            "bands",
            "ν avg.",
        ],
    )
