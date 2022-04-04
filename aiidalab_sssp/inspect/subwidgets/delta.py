import ipywidgets as ipw
import matplotlib.pyplot as plt
import numpy as np
import traitlets
from IPython.display import clear_output, display


class EOSwidget(ipw.VBox):

    selected_pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.select = ipw.Dropdown()
        self.select.observe(self._on_select, names="value")

        self.eos_out = ipw.Output()

        super().__init__(
            children=[
                ipw.HTML("EOS w.r.t AE"),
                self.select,
                self.eos_out,
            ],
        )

    @traitlets.observe("selected_pseudos")
    def _on_pseudos_change(self, change):
        if change["new"]:
            self.select.options = [i for i in self.selected_pseudos.keys()]

    def _on_select(self, change):

        if change["new"]:
            label = change["new"]
            pseudo_delta = self.selected_pseudos[label]["delta_measure"]
            del pseudo_delta["output_parameters"]
            fig = pseudo_eos_galary(pseudo_delta)

            with self.eos_out:
                clear_output()
                display(fig.canvas)


def get_ax_from_list(pos, axes_list):
    num_rows = len(axes_list)
    num_columns = len(axes_list[0])
    assert num_rows * num_columns == 10

    row = pos // 5
    column = pos % 5

    return axes_list[row, column]


def pseudo_eos_galary(delta_measure):
    """input delta_measure result of a pseudo plot 2x5 grids of EOS"""
    num_rows = 2
    num_cols = 5

    px = 1 / plt.rcParams["figure.dpi"]
    fig, axes_list = plt.subplots(num_rows, num_cols, figsize=(1024 * px, 640 * px))

    for idx, (configuration, res) in enumerate(delta_measure.items()):
        ax = get_ax_from_list(pos=idx, axes_list=axes_list)
        _plot_for(
            ax,
            configuration,
            res,
        )

    return fig


def _plot_for(ax, configuration, res):
    volumes = list(res["eos"]["output_volume_energy"]["volumes"].values())
    energies = list(res["eos"]["output_volume_energy"]["energies"].values())

    dense_volume_max = max(volumes)
    dense_volume_min = min(volumes)

    dense_volumes = np.linspace(dense_volume_min, dense_volume_max, 100)

    # TODO: in the results now only sample E0 is record, should use AE ref E0
    E0 = res["eos"]["output_birch_murnaghan_fit"]["energy0"]
    ref_V0, ref_B0, ref_B01 = res["output_parameters"]["reference_wien2k_V0_B0_B1"]
    V0, B0, B01 = res["output_parameters"]["birch_murnaghan_results"]

    ref_eos_fit_energy = birch_murnaghan(
        V=dense_volumes,
        E0=E0,
        V0=ref_V0,
        B0=ref_B0,
        B01=ref_B01,
    )
    compare_eos_fit_energy = birch_murnaghan(
        V=dense_volumes,
        E0=E0,
        V0=V0,
        B0=B0,
        B01=B01,
    )

    # Plot EOS: this will be done anyway
    ax.plot(volumes, energies, "ob", label="EOS data")
    ax.plot(dense_volumes, ref_eos_fit_energy, "-b", label="AE WIEN2K fit")
    ax.axvline(V0, linestyle="--", color="gray")

    ax.plot(dense_volumes, compare_eos_fit_energy, "-r", label=f"{configuration} fit")
    ax.fill_between(
        dense_volumes,
        ref_eos_fit_energy,
        compare_eos_fit_energy,
        alpha=0.5,
        color="red",
    )

    ax.legend(loc="upper center")
    ax.set_xlabel("Cell volume per formula unit ($\\AA^3$)")
    ax.set_ylabel("$E - TS$ per formula unit (eV)")


def birch_murnaghan(V, E0, V0, B0, B01):
    """
    Return the energy for given volume (V - it can be a vector) according to
    the Birch Murnaghan function with parameters E0,V0,B0,B01.
    """
    r = (V0 / V) ** (2.0 / 3.0)
    return E0 + 9.0 / 16.0 * B0 * V0 * (
        (r - 1.0) ** 3 * B01 + (r - 1.0) ** 2 * (6.0 - 4.0 * r)
    )
