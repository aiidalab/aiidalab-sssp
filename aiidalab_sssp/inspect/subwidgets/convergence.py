import ipywidgets as ipw
import traitlets
from aiida_sssp_workflow.utils import get_protocol
from IPython.display import clear_output, display
from matplotlib import pyplot as plt

from aiidalab_sssp.inspect import _px, cmap, extract_element, parse_label
from aiidalab_sssp.inspect.subwidgets.summary import SummaryWidget


def get_threshold(property_name) -> dict:
    """Get threshold for plot from protocol

    return a dict of upper bound of criteria
    """
    protocol = get_protocol("criteria")
    threshold = {}
    for key, value in protocol.items():
        threshold[key] = max(value[property_name]["bounds"])

    return threshold


property_map = {
    "Cohesive energy (Absolute Error, meV/atom)": {
        "name": "cohesive_energy",
        "measure": "absolute_diff",
        "ylabel": "Absolute error per atom (meV/atom)",
        "threshold": get_threshold("cohesive_energy"),
    },
    "Cohesive energy (Raw Energy, meV/atom)": {
        "name": "cohesive_energy",
        "measure": "cohesive_energy_per_atom",
        "ylabel": "Cohesive energy per atom (meV/atom)",
    },
    "Phonon frequencies (Relative Error, %)": {
        "name": "phonon_frequencies",
        "measure": "relative_diff",
        "ylabel": "Relative error (%)",
        "threshold": get_threshold("phonon_frequencies"),
    },
    "Phonon frequencies (Max freq error, cm-1)": {
        "name": "phonon_frequencies",
        "measure": "absolute_max_diff",
        "ylabel": "Max frequencies error, cm-1",
    },
    "Phonon frequencies (Max frequencies, cm-1)": {
        "name": "phonon_frequencies",
        "measure": "omega_max",
        "ylabel": "Max frequencies, cm-1",
    },
    "Pressure (Relative Error, %)": {
        "name": "pressure",
        "measure": "relative_diff",
        "ylabel": "Relative error (%)",
        "threshold": get_threshold("pressure"),
    },
    "Bands distance (Avg. error meV)": {
        "name": "bands",
        "measure": "eta_c",
        "ylabel": r"$Avg. Error of \eta_c (meV)$",
        "threshold": get_threshold("bands"),
    },
    "Bands distance (Max. error meV)": {
        "name": "bands",
        "measure": "max_diff_c",
        "ylabel": r"$Max Error of \eta_v (meV)$",
    },
    "Delta (Relative Error, %)": {
        "name": "delta",
        "measure": "relative_diff",
        "ylabel": "Relative error (%)",
        "threshold": get_threshold("delta"),
    },
    "Delta (Raw value, meV/cell)": {
        "name": "delta",
        "measure": "delta",
        "ylabel": r"$\Delta$ value (meV/cell)",
    },
}


class ConvergenceWidget(ipw.VBox):

    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):

        # using raido button widget so user only choose one proper to check
        # at one time. It can be more, but pollute the UX and not useful.
        self.property_select = ipw.RadioButtons(
            options=list(property_map.keys()),
            value=list(property_map.keys())[0],
        )
        self.property_select.observe(self._on_property_select_change, names="value")
        self.summary = SummaryWidget()
        self.summary.observe(
            self._on_summary_criteria_change, names="selected_criteria"
        )
        ipw.dlink((self, "pseudos"), (self.summary, "pseudos"))

        self.out = ipw.Output()  # out figure
        self.convergence = ipw.VBox(
            children=[
                self.property_select,
                self.out,
            ],
        )

        self.summary_accordion = ipw.Accordion(
            children=[self.summary], selected_index=None
        )
        self.summary_accordion.set_title(
            0, "Toggle to show the summary of verification results."
        )
        self.convergence_accordion = ipw.Accordion(
            children=[self.convergence], selected_index=None
        )
        self.convergence_accordion.set_title(
            0, "Toggle to show the detailed convergence verification results."
        )
        self.convergence_accordion.observe(
            self._on_convergence_accordion_change, names="selected_index"
        )
        self.accordions = ipw.VBox(
            children=[
                self.summary_accordion,
                self.convergence_accordion,
            ]
        )
        self.accordions.layout.visibility = "hidden"

        self.help_message = ipw.HTML("<h2> Convergence results </h2>")
        self.help_message.layout.visibility = "hidden"

        super().__init__(
            children=[
                self.help_message,
                self.accordions,
            ]
        )

    def _on_summary_criteria_change(self, change):
        """When select new criteria on summary widget"""
        if change["new"]:
            self._render()

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):
        """only update plot when accordion open"""
        if change["new"]:
            self.accordions.layout.visibility = "visible"
            self.help_message.layout.visibility = "visible"
            self.convergence_accordion.selected_index = None
        else:
            self.accordions.layout.visibility = "hidden"
            self.help_message.layout.visibility = "hidden"

    def _on_convergence_accordion_change(self, change):
        # only render when accordion open up
        if change["new"] == 0:
            self._render()

    def _on_property_select_change(self, change):
        if change["new"]:
            self._render()

    def _render(self):
        """render the plot"""
        property_selected = self.property_select.value

        fig, (ax_wfc, ax_rho) = plt.subplots(
            2,
            1,
            gridspec_kw={"wspace": 0.00, "hspace": 0.40},
            figsize=(1024 * _px, 600 * _px),
        )
        fig.canvas.header_visible = False
        self._render_plot(ax_wfc, ax_rho, property_selected)

        with self.out:
            clear_output(wait=True)
            display(fig.canvas)

    def _render_plot(self, ax_wfc, ax_rho, property):
        """Actual render of plot"""
        wfname = property_map[property]["name"]
        measure = property_map[property]["measure"]
        element = extract_element(self.pseudos)

        for label, pseudo_out in self.pseudos.items():
            # TODO: Calculate the one delta measure and attach to label value
            try:
                res = pseudo_out["convergence"][wfname]
                x_wfc = res["output_parameters_wfc_test"]["ecutwfc"]
                y_wfc = res["output_parameters_wfc_test"][measure]

                x_rho = res["output_parameters_rho_test"]["ecutrho"]
                y_rho = res["output_parameters_rho_test"][measure]

                wavefunction_cutoff = res["output_parameters"]["wavefunction_cutoff"]
            except KeyError:
                # usually the convergence test on the property is not finished okay
                continue  # TODO give more detailed messages

            # plot
            pseudo_info = parse_label(label)

            # TODO label include delta info
            ax_wfc.plot(
                x_wfc,
                y_wfc,
                marker="^",
                markersize=2,
                color=cmap(pseudo_info),
                label=pseudo_info["representive_label"],
            )
            ax_rho.plot(
                x_rho,
                y_rho,
                marker="^",
                markersize=2,
                color=cmap(pseudo_info),
                label=f"{wavefunction_cutoff} Ry",
            )

        # ax_wfc.set_ylabel(property_map[property]['ylabel'])
        ax_wfc.set_xlabel("Wavefuntion cutoff (Ry)")
        ax_wfc.set_title(
            f"Convergence verification on element {element} (dual=4 for NC and dual=8 for non-NC)"
        )
        ax_wfc.legend(loc="upper right", prop={"size": 6})

        ax_rho.set_ylabel(property_map[property]["ylabel"])
        ax_rho.yaxis.set_label_coords(-0.05, 0.9)
        ax_rho.set_xlabel("Charge density cudoff (Ry)")
        ax_rho.set_title("Convergence test at fixed wavefunction cutoff")
        ax_rho.legend(loc="upper right", prop={"size": 6})

        _criteria = str.lower(self.summary.selected_criteria)
        threshold = property_map[property].get("threshold", {}).get(_criteria, None)
        if threshold:
            ax_wfc.axhline(y=threshold, color="r", linestyle="--")
            ax_rho.axhline(y=threshold, color="r", linestyle="--")

        #     ax_wfc.set_ylim(-0.5 * threshold, 10 * threshold)
        #     ax_rho.set_ylim(-0.5 * threshold, 10 * threshold)
