import ipywidgets as ipw
import pandas as pd
import traitlets
from aiida_sssp_workflow.workflows.verifications import (
    DEFAULT_CONVERGENCE_PROPERTIES_LIST,
)
from IPython.display import clear_output, display

from aiidalab_sssp.inspect import extract_element, get_conf_list, parse_label


class SummaryWidget(ipw.VBox):
    """Summary of verification"""

    pseudos = traitlets.Dict(allow_none=True)
    selected_criteria = traitlets.Unicode()

    def __init__(self):
        # Delta mesure
        self.accuracy_summary = ipw.Output()
        self.convergence_summary = ipw.Output()

        self.toggle_criteria = ipw.ToggleButtons(
            options=["Efficiency", "Precision"],
            value="Efficiency",
            tooltip="Toggle to switch criteria.",
        )
        self.toggle_criteria.observe(self._on_toggle_criteria_change)
        ipw.dlink((self.toggle_criteria, "value"), (self, "selected_criteria"))

        self._show_rho = False
        self._show_dual = False
        self.toggle_show_dual_or_rho = ipw.ToggleButtons(
            options=["Default", "Show ρ cutoff", "Show dual"],
            value="Default",
            # description="Show extra cutoff information",
            disabled=False,
            tooltip="Toggle show rho or dual value",
        )
        self.toggle_show_dual_or_rho.observe(
            self._on_toggle_show_dual_or_rho_change, names="value"
        )

        super().__init__(
            children=[
                self.accuracy_summary,
                self.convergence_summary,
                ipw.HTML("<p> Switch criteria to: </p>"),
                self.toggle_criteria,
                ipw.HTML("<p> Show ρ or dual </p>"),
                self.toggle_show_dual_or_rho,
            ],
        )

    def _on_toggle_show_dual_or_rho_change(self, change):
        if change["new"] == "Show ρ cutoff":
            self._show_dual = False
            self._show_rho = True
        elif change["new"] == "Show dual":
            self._show_rho = False
            self._show_dual = True
        else:
            self._show_dual = False
            self._show_rho = False
        with self.convergence_summary:
            clear_output(wait=True)
            display(self._render_convergence())

    def _on_toggle_criteria_change(self, _):
        with self.convergence_summary:
            clear_output(wait=True)
            display(self._render_convergence())

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):
        if change["new"]:
            self.layout.visibility = "visible"
            with self.accuracy_summary:
                clear_output(wait=True)
                display(self._render_accuracy())

            with self.convergence_summary:
                clear_output(wait=True)
                display(self._render_convergence())
        else:
            self.layout.visibility = "hidden"

    def _render_accuracy(self):
        rows = []
        element = extract_element(self.pseudos)
        conf_list = get_conf_list(element)
        columns = ["label"] + conf_list
        for label, pseudo_out in self.pseudos.items():
            _data = pseudo_out["accuracy"]["delta"]["output_parameters"]
            nu_list = [
                round(_data.get(i, {}).get("nu/natoms", None), 3) for i in conf_list
            ]

            output_label = parse_label(label)["representive_label"]
            rows.append([output_label, *nu_list])

        df = pd.DataFrame(rows, columns=columns)
        df.style.hide_index()
        return df

    def _render_convergence(self):
        rows = []
        prop_list = [i.split(".")[1] for i in DEFAULT_CONVERGENCE_PROPERTIES_LIST]
        columns = ["label"] + [i.replace("_", " ") for i in prop_list]
        for label, pseudo_out in self.pseudos.items():
            _data = pseudo_out["convergence"]
            cutoffs = []
            for prop in prop_list:
                # We didn't not relly run the convergence on rho at precision criteria
                # The trick here is the wft cutoff of rho cutoff is write and used,
                # The dual is from wfccut/rhocut of efficiency criteria, and also applied to
                # precision results display. The rhocut is derived then from rhocut=wfccut * dual.
                wfc_cutoff = (
                    _data.get(prop, {})
                    .get("output_parameters", {})
                    .get("wavefunction_cutoff", None)
                )
                rho_cutoff = (
                    _data.get(prop, {})
                    .get("output_parameters", {})
                    .get("chargedensity_cutoff", None)
                )
                wfc_cutoff = int(wfc_cutoff) if wfc_cutoff else "nan"
                rho_cutoff = int(rho_cutoff) if rho_cutoff else "nan"
                # compute dual. The dual is same for both precision and efficiency
                try:
                    dual = round(rho_cutoff / wfc_cutoff, 1)
                except Exception:
                    dual = "nan"

                # if checking precision, update cutoff pair first
                if self.toggle_criteria.value == "Precision":
                    wfc_cutoff = (
                        _data.get(prop, {})
                        .get("output_parameters", {})
                        .get("all_criteria_wavefunction_cutoff", {})
                        .get("precision", None)
                    )
                    wfc_cutoff = int(wfc_cutoff) if wfc_cutoff else "nan"
                    try:
                        rho_cutoff = int(wfc_cutoff * dual)
                    except Exception:
                        rho_cutoff = "nan"

                    if not wfc_cutoff:
                        cutoffs.append(str("nan"))
                        continue

                # not allow to show at the same time
                assert not (self._show_dual and self._show_rho)
                if self._show_rho:
                    cutoffs.append(f"{wfc_cutoff} ({rho_cutoff})")
                elif self._show_dual:
                    cutoffs.append(f"{wfc_cutoff} ({dual})")
                else:
                    cutoffs.append(f"{wfc_cutoff}")

            output_label = parse_label(label)["representive_label"]
            rows.append([output_label, *cutoffs])

        df = pd.DataFrame(rows, columns=columns)
        df.style.hide_index()
        return df
