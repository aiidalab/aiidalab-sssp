import ipywidgets as ipw
import traitlets
from IPython.display import clear_output


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

                print_summary(change["new"])


def print_summary(pseudos: dict):

    print("Label\t\t\t|Cohesive energy|\t|Phonon frequencies|\t|Pressure|")
    for label, output in pseudos.items():
        try:
            res_coh = output["convergence_cohesive_energy"]["final_output_parameters"]
            res_phonon = output["convergence_phonon_frequencies"][
                "final_output_parameters"
            ]
            res_pressure = output["convergence_pressure"]["final_output_parameters"]
            print(
                f'{label}\t({res_coh["wfc_cutoff"]}, {res_coh["rho_cutoff"]:.2f})'
                f'\t({res_phonon["wfc_cutoff"]}, {res_phonon["rho_cutoff"]:.2f})'
                f'\t({res_pressure["wfc_cutoff"]}, {res_pressure["rho_cutoff"]:.2f})'
            )
        except Exception as e:
            raise e
