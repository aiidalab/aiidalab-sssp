import ipywidgets as ipw
import traitlets
from IPython.display import clear_output, display
from matplotlib import pyplot as plt

from aiidalab_sssp.inspect import _px, cmap, parse_label
from aiidalab_sssp.inspect.subwidgets.summary import SummaryWidget

property_map = {
    "Cohesive energy": {
        "name": "cohesive_energy",
        "measure": "absolute_diff",
        "ylabel": "Absolute error per atom (meV/atom)",
    },
    "Phonon frequencies": {
        "name": "phonon_frequencies",
        "measure": "relative_diff",
        "ylabel": "Relative error (%)",
    },
    "Pressure": {
        "name": "pressure",
        "measure": "relative_diff",
        "ylabel": "Relative error (%)",
    },
    "Bands distance": {
        "name": "bands",
        "measure": "eta_c",
        "ylabel": r"$Error of \eta_c (meV)$",
    },
    "Delta": {
        "name": "delta",
        "measure": "relative_diff",
        "ylabel": "Relative error (%)",
    },
}


class ConvergenceWidget(ipw.VBox):

    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):

        # using raido button widget so user only choose one proper to check
        # at one time. It can be more, but pollute the UX and not useful.
        self.property_select = ipw.RadioButtons(
            options=[
                "Cohesive energy",
                "Phonon frequencies",
                "Pressure",
                "Delta",
                "Bands distance",
            ],
            value="Cohesive energy",
        )
        self.property_select.observe(self._on_property_select_change, names="value")
        self.summary = SummaryWidget()
        ipw.dlink((self, "pseudos"), (self.summary, "pseudos"))

        self.out = ipw.Output()  # out figure
        self.convergence = ipw.VBox(
            children=[
                self.summary,
                self.property_select,
                self.out,
            ],
        )

        self.accordion = ipw.Accordion(children=[self.convergence], selected_index=None)
        self.accordion.set_title(
            0, "Toggle to show the detailed convergence verification results."
        )
        self.accordion.observe(self._on_accordion_change, names="selected_index")

        super().__init__(
            children=[
                ipw.HTML("<h2> Convergence results </h2>"),
                self.accordion,
            ]
        )

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):
        """only update plot when accordion open"""
        self.accordion.selected_index = None

    def _on_accordion_change(self, change):
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
            "Fixed rho cutoff at 200 * dual (dual=4 for NC and dual=8 for non-NC)"
        )
        ax_wfc.legend(loc="upper right", prop={"size": 6})

        ax_rho.set_ylabel(property_map[property]["ylabel"])
        ax_rho.yaxis.set_label_coords(-0.05, 0.9)
        ax_rho.set_xlabel("Charge density cudoff (Ry)")
        ax_rho.set_title("Convergence test at fixed wavefunction cutoff")
        ax_rho.legend(loc="upper right", prop={"size": 6})

        # if threshold:
        #     ax_wfc.axhline(y=threshold, color="r", linestyle="--")
        #     ax_rho.axhline(y=threshold, color="r", linestyle="--")

        #     ax_wfc.set_ylim(-0.5 * threshold, 10 * threshold)
        #     ax_rho.set_ylim(-0.5 * threshold, 10 * threshold)
