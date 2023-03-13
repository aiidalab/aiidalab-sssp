import ipywidgets as ipw
import traitlets
from IPython.display import clear_output, display

from aiidalab_sssp.inspect.plot_utils import convergence


class _PlotConvergenBaseWidget(ipw.VBox):
    selected_pseudos = traitlets.Dict(allow_none=True)

    _WF = "Not implement"
    _MEASURE = "Not implement"
    _YLABEL = "Not implement"
    _THRESHOLD = None

    def __init__(self):
        # output widget
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
                fig = convergence(
                    change["new"],
                    wf_name=self._WF,
                    measure_name=self._MEASURE,
                    ylabel=self._YLABEL,
                    threshold=self._THRESHOLD,
                )
                fig.canvas.header_visible = False
                display(fig.canvas)


class PlotCohesiveEnergyConvergeWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_cohesive_energy"
    _MEASURE = "cohesive_energy_per_atom"
    _YLABEL = "Cohesive Energy per atom (meV/atom)"
    _THRESHOLD = None


class PlotCohesiveEnergyConvergeDiffWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_cohesive_energy"
    _MEASURE = "absolute_diff"
    _YLABEL = "Cohesive Energy per atom (absolute error, meV/atom)"
    _THRESHOLD = 2.0


class PlotPhononFrequenciesConvergeAbsWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_phonon_frequencies"
    _MEASURE = "absolute_diff"
    _YLABEL = "Phonon frequencies ω (absolute error, cm-1)"
    _THRESHOLD = None


class PlotPhononFrequenciesConvergeRelWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_phonon_frequencies"
    _MEASURE = "relative_diff"
    _YLABEL = "Phonon frequencies ω (relative error, %)"
    _THRESHOLD = 2.0


class PlotPressureConvergeWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_pressure"
    _MEASURE = "pressure"
    _YLABEL = "Pressure (GPa)"
    _THRESHOLD = None


class PlotPressureConvergeRelWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_pressure"
    _MEASURE = "relative_diff"
    _YLABEL = "Pressure (relative error, %)"
    _THRESHOLD = 1.0


class PlotDeltaConvergeWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_delta"
    _MEASURE = "delta"
    _YLABEL = "Δ -factor (meV)"
    _THRESHOLD = None


class PlotDeltaConvergeRelWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_delta"
    _MEASURE = "relative_diff"
    _YLABEL = "Delta (relative error, %)"
    _THRESHOLD = 2.0


class PlotBandsConvergeWidget(_PlotConvergenBaseWidget):
    _WF = "convergence_bands"
    _MEASURE = "eta_c"
    _YLABEL = "η up above fermi energe 5 eV (meV)"
    _THRESHOLD = 20.0
