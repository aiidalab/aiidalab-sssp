"""Moudle contains widgets for accuracy delat results inspect.
The widget EosComparisonWidget for compare Eos fit line of a given pseudos in the given configuration.
The widget AccuracyMeritWidget showing Nicola's Nu measure of all pseudos in all configurations"""
import ipywidgets as ipw
import matplotlib.pyplot as plt
import numpy as np
import traitlets
from aiida_sssp_workflow.calculations.calculate_delta import rel_errors_vec_length
from IPython.display import clear_output, display

from aiidalab_sssp.inspect import _px, cmap, extract_element, parse_label
from aiidalab_sssp.inspect.subwidgets.utils import CONFIGURATIONS


def birch_murnaghan(V, E0, V0, B0, B01):
    """
    Return the energy for given volume (V - it can be a vector) according to
    the Birch Murnaghan function with parameters E0,V0,B0,B01.
    """
    r = (V0 / V) ** (2.0 / 3.0)
    return E0 + 9.0 / 16.0 * B0 * V0 * (
        (r - 1.0) ** 3 * B01 + (r - 1.0) ** 2 * (6.0 - 4.0 * r)
    )


class AccuracyMeritWidget(ipw.VBox):
    """Widget for showing accuracy merit of a given pseudo over all configuration.
    The merit can be either nu or delta.
    """

    pseudos = traitlets.Dict(allow_none=True)
    merit_type = traitlets.Unicode(default_value="nu")

    def __init__(self):
        self.out_plot = ipw.Output()

        super().__init__(
            children=[
                self.out_plot,
            ],
        )

    @traitlets.observe("merit_type")
    def _on_merit_type_change(self, change):
        if change["new"]:
            self.update_plot()

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):
        """Update the plot when pseudos are changed."""
        if change["new"]:
            self.layout.display = "block"
            self.update_plot()
        else:
            self.layout.display = "none"

    def update_plot(self):
        """Update the plot with the current pseudos and measure type."""
        with self.out_plot:
            clear_output()
            fig = self._render_plot(self.pseudos, self.merit_type)
            fig.canvas.header_visible = False
            display(fig.canvas)

    @staticmethod
    def _render_plot(pseudos: dict, measure_type):
        """Render the plot for the given pseudos and measure type."""
        fig, ax = plt.subplots(1, 1, figsize=(1024 * _px, 360 * _px))
        # conf_list store configuration list of every pseudo
        conf_list = {}
        for label, data in pseudos.items():
            _data = data["accuracy"]["delta"]
            conf_list[label] = [
                i for i in CONFIGURATIONS if i in _data.keys() and i != "TYPICAL"
            ]

        # element
        element = extract_element(pseudos)

        if measure_type == "delta":
            ylabel = "Δ -factor"
        elif measure_type == "nu":
            ylabel = "ν -factor"

        xticklabels = []

        for i, (label, output) in enumerate(pseudos.items()):
            # update xticklabel to include all configurations in output
            if len(xticklabels) < len(conf_list[label]):
                xticklabels = conf_list[label]

            width = 0.6 / len(pseudos)

            y_delta = []
            for configuration in conf_list[label]:
                res = output["accuracy"]["delta"][configuration]["output_parameters"]
                if measure_type == "delta":
                    y_delta.append(res["delta/natoms"])
                if measure_type == "nu":
                    v0w, b0w, b1w = res["birch_murnaghan_results"]
                    v0f, b0f, b1f = res["reference_wien2k_V0_B0_B1"]
                    nu = rel_errors_vec_length(v0w, b0w, b1w, v0f, b0f, b1f)
                    y_delta.append(nu)

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

        if max(y_delta) < 8.0:
            y_max = 10 / 8.0 * max(y_delta)
        else:
            y_max = 10.0

        ax.legend(loc="upper left", prop={"size": 10})
        ax.axhline(y=1.0, linestyle="--", color="gray")
        ax.set_ylabel(ylabel)
        ax.set_ylim([0, y_max])
        ax.set_xticks(range(len(xticklabels)))
        ax.set_xticklabels(xticklabels)

        return fig


class EosComparisonWidget(ipw.VBox):
    """This widget is used to compare the equation of state of two different
    pseudopotentials.
    Two subplots are shown for two different pseudopotentials. The drowdown menu
    allows user to select the pseudopotential and configuration.
    """

    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.select_pseudo_ref = ipw.Dropdown()
        self.select_pseudo_ref.observe(self._on_pseudo_select, names="value")

        self.select_pseudo_comp = ipw.Dropdown()
        self.select_pseudo_comp.observe(self._on_pseudo_select, names="value")

        self.select_configuration = ipw.Dropdown()
        self.select_configuration.observe(self._on_configuration_change, names="value")

        self.eos_preview = ipw.Output()  # empty plot with a instruction ask for select

        super().__init__(
            children=[
                ipw.HBox(
                    children=[
                        self.select_pseudo_ref,
                        self.select_pseudo_comp,
                    ]
                ),
                self.select_configuration,
                self.eos_preview,
            ],
        )

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):
        if change["new"] is not None and len(change["new"]) > 0:
            self.layout.display = "block"
            with self.hold_trait_notifications():
                pseudo_list = list(self.pseudos.keys())
                self.select_pseudo_ref.options = pseudo_list
                self.select_pseudo_comp.options = pseudo_list

            self.update_plot()
        else:
            self.layout.display = "none"

    def _on_pseudo_select(self, _):
        """Update configuration dropdown options"""
        label_ref = self.select_pseudo_ref.value
        label_comp = self.select_pseudo_comp.value

        if label_ref is None or label_comp is None:
            return

        _data_ref = self.pseudos[label_ref]["accuracy"]["delta"]
        _data_comp = self.pseudos[label_comp]["accuracy"]["delta"]

        # The configuration list is the intersection of two pseudos
        self.select_configuration.options = [
            i
            for i in CONFIGURATIONS
            if i in _data_ref.keys() and i in _data_comp.keys()
        ]

        self.update_plot()

    def update_plot(self):
        """Trigger plot update"""
        label_ref = self.select_pseudo_ref.value
        label_comp = self.select_pseudo_comp.value
        configuration = self.select_configuration.value

        data_ref = self.pseudos[label_ref]["accuracy"]["delta"].get(configuration, None)
        data_comp = self.pseudos[label_comp]["accuracy"]["delta"].get(
            configuration, None
        )

        with self.eos_preview:
            clear_output(wait=True)
            fig = self._render_plot(
                data_ref, data_comp, configuration, titles=(label_ref, label_comp)
            )
            fig.canvas.header_visible = False
            display(fig.canvas)

    def _on_configuration_change(self, change):
        """Update eos preview"""
        if change["new"] is not None:
            self.update_plot()

    @staticmethod
    def _render_plot(data_ref, data_comp, configuration, titles=("EOS", "EOS")):
        """render preview of EOS comparison result."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(1024 * _px, 440 * _px))

        # plot to ax1
        plot_eos(ax1, data_ref, configuration, title=titles[0])
        # plot to ax2
        plot_eos(ax2, data_comp, configuration, title=titles[1])

        return fig


def plot_eos(ax, data, configuration, title="EOS"):
    """plot EOS result on ax"""
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
    ax.plot(dense_volumes, ae_eos_fit_energy, "-b", label="AE reference")
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
    nu = rel_errors_vec_length(ref_V0, ref_B0, ref_B01, V0, B0, B01)
    nu = round(nu, 3)
    delta = round(data["output_parameters"]["delta/natoms"], 3)
    ax.text(center_x, center_y, f"$\\nu$={nu}\n$\\Delta$={delta} meV/atom")

    ax.legend(loc="upper center")
    ax.set_xlabel("Cell volume per formula unit ($\\AA^3$)", fontsize=8)
    ax.set_ylabel("$E - TS$ per formula unit (eV)", fontsize=8)
    ax.get_yaxis().set_ticks([])
    ax.set_title(title, fontsize=8)
