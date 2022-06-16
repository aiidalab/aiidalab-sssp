"""Moudle contains widgets for accuracy delat results inspect.
The widget EosWidget for showing Eos fit line of a given pseudo in the given configuration.
The widget NuMeasure showing Nicola's Nu measure of all pseudos in all configurations"""
import ipywidgets as ipw
import matplotlib.pyplot as plt
import numpy as np
import traitlets
from aiida_sssp_workflow.utils import OXIDE_CONFIGURATIONS, UNARIE_CONFIGURATIONS
from IPython.display import clear_output, display

from aiidalab_sssp.inspect import _px, cmap, extract_element, parse_label

CONFIGURATIONS = OXIDE_CONFIGURATIONS + UNARIE_CONFIGURATIONS + ["RE", "TYPICAL"]


def birch_murnaghan(V, E0, V0, B0, B01):
    """
    Return the energy for given volume (V - it can be a vector) according to
    the Birch Murnaghan function with parameters E0,V0,B0,B01.
    """
    r = (V0 / V) ** (2.0 / 3.0)
    return E0 + 9.0 / 16.0 * B0 * V0 * (
        (r - 1.0) ** 3 * B01 + (r - 1.0) ** 2 * (6.0 - 4.0 * r)
    )


class NuMeasure(ipw.VBox):

    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.out_nu = ipw.Output()
        self.out_delta = ipw.Output()

        # measure button
        self.measure_tab = ipw.Tab()
        self.measure_tab.set_title(0, "ν-factor")
        self.measure_tab.set_title(1, "Δ-factor")

        self.measure_tab.children = [self.out_nu, self.out_delta]

        super().__init__(
            children=[
                self.measure_tab,
            ],
        )

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):

        if change["new"]:
            self.layout.visibility = "visible"
            with self.out_nu:
                clear_output()
                fig = self._render_plot(change["new"], "nu")
                fig.canvas.header_visible = False
                display(fig.canvas)

            with self.out_delta:
                clear_output()
                fig = self._render_plot(change["new"], "delta")
                fig.canvas.header_visible = False
                display(fig.canvas)
        else:
            self.layout.visibility = "hidden"

    @staticmethod
    def _render_plot(pseudos: dict, measure_type):

        px = 1 / plt.rcParams["figure.dpi"]  # pixel in inches
        fig, ax = plt.subplots(1, 1, figsize=(1024 * px, 360 * px))
        # conf_list store configuration list of every pseudo
        conf_list = {}
        for label, data in pseudos.items():
            _data = data["accuracy"]["delta"]
            conf_list[label] = [i for i in _data.keys() if i in CONFIGURATIONS]

        # element
        element = extract_element(pseudos)

        if measure_type == "delta":
            keyname = "delta/natoms"
            ylabel = "Δ -factor"
        elif measure_type == "nu":
            keyname = "nu/natoms"
            ylabel = "ν -factor"

        xticklabels = []
        for i, (label, output) in enumerate(pseudos.items()):
            # update xticklabel to include all configurations in output
            if len(xticklabels) < len(conf_list[label]):
                xticklabels = conf_list[label]

            width = 0.05  # the width of the bars

            y_delta = []
            for configuration in conf_list[label]:
                res = output["accuracy"]["delta"]["output_parameters"][configuration]
                y_delta.append(res[keyname])

            x = np.arange(len(conf_list[label]))
            pseudo_info = parse_label(label)

            ax.bar(
                x + width * i,
                y_delta,
                width,
                color=cmap(pseudo_info),
                edgecolor="black",
                linewidth=1,
                label=pseudo_info["representive_label"],
            )
            ax.set_title(f"X={element}")

        ax.legend(loc="upper left", prop={"size": 6})
        ax.axhline(y=1.0, linestyle="--", color="gray")
        ax.set_ylabel(ylabel)
        ax.set_ylim([0, 10])
        ax.set_yticks(np.arange(10))
        ax.set_xticks(range(len(xticklabels)))
        ax.set_xticklabels(xticklabels)

        return fig


class EosWidget(ipw.VBox):

    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.select_pseudo = ipw.Dropdown()
        self.select_pseudo.observe(self._on_pseudo_select, names="value")

        self.select_configuration = ipw.Dropdown()
        self.select_configuration.observe(self._on_configuration_selecet, names="value")

        self.eos_preview = ipw.Output()  # empty plot with a instruction ask for select

        super().__init__(
            children=[
                # ipw.HTML("<h2> Equation of State Pseudopotential w.r.t AE </h2>"),
                ipw.HBox(children=[self.select_pseudo, self.select_configuration]),
                self.eos_preview,
            ],
        )

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):
        if change["new"]:
            self.layout.visibility = "visible"
            self.select_pseudo.options = list(self.pseudos.keys())
        else:
            self.layout.visibility = "hidden"

    def _on_pseudo_select(self, change):
        """Update configuration dropdown list and select first entity"""
        if change["new"]:
            label = change["new"]
            _data = self.pseudos[label]["accuracy"]["delta"]

            configuration_list = [i for i in _data.keys() if i in CONFIGURATIONS]
            self.select_configuration.options = configuration_list

            self._render()

    def _on_configuration_selecet(self, change):
        """Update eos preview"""
        if change["new"]:
            self._render()

    def _render(self):
        """once called render plot with current instance"""
        output = self.eos_preview
        label = self.select_pseudo.value
        configuration = self.select_configuration.value

        data = self.pseudos[label]["accuracy"]["delta"].get(configuration, None)
        fig, ax = plt.subplots(1, 1, figsize=(440 * _px, 400 * _px))
        fig.canvas.header_visible = False
        self._render_plot(ax, data=data, configuration=configuration)

        with output:
            clear_output(wait=True)
            display(fig.canvas)

    @staticmethod
    def _render_plot(ax, data, configuration):
        """render preview of eos result"""
        volumes = data["eos"]["output_volume_energy"]["volumes"]
        energies = data["eos"]["output_volume_energy"]["energies"]

        dense_volume_max = max(volumes)
        dense_volume_min = min(volumes)

        dense_volumes = np.linspace(dense_volume_min, dense_volume_max, 100)

        E0 = data["eos"]["output_birch_murnaghan_fit"]["energy0"]
        ref_V0, ref_B0, ref_B01 = data["output_parameters"]["reference_wien2k_V0_B0_B1"]
        V0, B0, B01 = data["output_parameters"]["birch_murnaghan_results"]

        ae_eos_fit_energy = birch_murnaghan(
            V=dense_volumes,
            E0=E0,  # in future update E0 from referece json, where ACWF has E0 stored.
            V0=ref_V0,
            B0=ref_B0,
            B01=ref_B01,
        )
        psp_eos_fit_energy = birch_murnaghan(
            V=dense_volumes,
            E0=E0,
            V0=V0,
            B0=B0,
            B01=B01,
        )

        # Plot EOS: this will be done anyway
        ax.tick_params(axis="y", labelsize=6, rotation=45)

        ax.plot(volumes, energies, "ob", label="RAW equation of state")
        ax.plot(dense_volumes, ae_eos_fit_energy, "-b", label="AE WIEN2K")
        ax.axvline(V0, linestyle="--", color="gray")

        ax.plot(dense_volumes, psp_eos_fit_energy, "-r", label=f"{configuration} fit")
        ax.fill_between(
            dense_volumes,
            ae_eos_fit_energy,
            psp_eos_fit_energy,
            alpha=0.5,
            color="red",
        )

        center_x = (max(volumes) + min(volumes)) / 2
        center_y = (max(energies) + min(energies)) / 2

        # write text of nu value in close middle
        nu = round(data["output_parameters"]["nu/natoms"], 3)
        delta = round(data["output_parameters"]["delta/natoms"], 3)
        plt.text(
            center_x, center_y, f"$\\nu$={nu} meV/atom\n$\\Delta$={delta} meV/atom"
        )

        ax.legend(loc="upper center")
        ax.set_xlabel("Cell volume per formula unit ($\\AA^3$)", fontsize=8)
        ax.set_ylabel("$E - TS$ per formula unit (eV)", fontsize=8)
