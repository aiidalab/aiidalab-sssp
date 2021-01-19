import ipywidgets as ipw
import numpy as np


def eos_birch_murnaghan(volume, E0, V0, B0, B1):
    'From Phys. Rev. B 70, 224107'
    eta = (volume / V0)**(2.0 / 3.0)
    E = E0 + 9.0 * B0 * V0 / 16.0 * (eta - 1.0)**2 * (6.0 + B1 *
                                                      (eta - 1.0) - 4.0 * eta)

    return E


class DeltaFactorResultViewer(ipw.VBox):
    """Viewer class for Delta factor result."""

    _PLOT_WIDTH = 400
    _PLOT_HEIGHT = 400
    _LINE_WIDTH = 2
    _REF_LINE_COLOR = 'green'
    _RES_COLOR = 'red'
    _CIRCLE_SIZE = 8

    def __init__(self,
                 title,
                 delta_value,
                 input_V0_B0_B1,
                 wien2k_V0_B0_B1,
                 volumes,
                 energies,
                 energy0,
                 volume_unit='A^3/atom',
                 energy_unit='eV/atom',
                 **kwargs):
        from bokeh.io import show, output_notebook
        from bokeh.plotting import figure
        from bokeh.models import Label
        output_notebook(hide_banner=True)
        out = ipw.Output()
        with out:
            # Extract relevant data
            x_min = min(volumes)
            x_max = max(volumes)
            x = np.arange(x_min, x_max, 0.02)

            V0_wien2k = wien2k_V0_B0_B1[0]
            B0_wien2k = wien2k_V0_B0_B1[1]
            B1_wien2k = wien2k_V0_B0_B1[2]
            y_wien2k = eos_birch_murnaghan(x, energy0, V0_wien2k,
                                           B0_wien2k / 160.2176487, B1_wien2k)

            V0 = input_V0_B0_B1[0]
            B0 = input_V0_B0_B1[1]
            B1 = input_V0_B0_B1[2]
            y_line = eos_birch_murnaghan(x, energy0, V0, B0 / 160.2176487, B1)

            x_axis_label = 'volume'
            x_unit = volume_unit
            y_axis_label = 'energies'
            y_unit = energy_unit
            # create a new plot with a log axis type
            plt = figure(title=title,
                         plot_width=self._PLOT_WIDTH,
                         plot_height=self._PLOT_HEIGHT,
                         sizing_mode="stretch_width",
                         x_axis_label=f'{x_axis_label} ({x_unit})',
                         y_axis_label=f'{y_axis_label} ({y_unit})')

            plt.line(x,
                     y_wien2k,
                     line_width=self._LINE_WIDTH,
                     line_color=self._REF_LINE_COLOR,
                     legend_label="wien2k")
            plt.line(x,
                     y_line,
                     line_width=self._LINE_WIDTH,
                     line_color=self._RES_COLOR,
                     legend_label="fit")
            plt.circle(volumes,
                       energies,
                       fill_color=self._RES_COLOR,
                       size=self._CIRCLE_SIZE)

            text = Label(x=self._PLOT_WIDTH / 2,
                         y=self._PLOT_HEIGHT / 2,
                         x_units='screen',
                         y_units='screen',
                         text=f'Δ = {delta_value:.3f} (meV/atom)',
                         render_mode='css',
                         border_line_color='black',
                         border_line_alpha=1.0,
                         background_fill_color='white',
                         background_fill_alpha=1.0)
            plt.add_layout(text)

            show(plt)
        children = [out]
        super().__init__(children, **kwargs)


class ConvergenceResultViewer(ipw.VBox):
    """Viewer cconvergence results."""
    _PLOT_WIDTH = 400
    _PLOT_HEIGHT = 360
    _LINE_WIDTH = 2
    _REF_LINE_COLOR = 'green'
    _RES_COLOR = 'red'
    _POINT_COLOR = 'navy'
    _POINT_FILL_COLOR = 'navy'
    _POINT_ALPHA = 0.3
    _CIRCLE_SIZE = 8

    def __init__(self,
                 x_data,
                 y_data,
                 x_limit,
                 converge_point,
                 converge_tol,
                 title='',
                 x_axis_label='',
                 y_axis_label='',
                 x_unit='',
                 y_unit='',
                 **kwargs):
        from bokeh.io import show, output_notebook
        from bokeh.plotting import figure
        from bokeh.models import BoxAnnotation, FixedTicker
        output_notebook(hide_banner=True)
        out = ipw.Output()
        with out:
            # create a new plot with a log axis type
            plt = figure(title=f'{y_axis_label} ({y_unit})',
                         plot_width=self._PLOT_WIDTH,
                         plot_height=self._PLOT_HEIGHT,
                         sizing_mode="stretch_width",
                         x_axis_label=f'{x_axis_label} ({x_unit})',
                         y_axis_label=f'({y_unit})')
            plt.x_range.end = x_limit

            plt.line(x_data,
                     y_data,
                     line_width=self._LINE_WIDTH,
                     line_color=self._RES_COLOR)
            plt.square(x_data,
                       y_data,
                       fill_color=self._RES_COLOR,
                       size=self._CIRCLE_SIZE)

            plt.xaxis.ticker = FixedTicker(ticks=list(x_data) + [x_limit])

            # plot the convergence point
            if converge_point:
                legend_label = f"converge at {converge_point[0]} {x_unit}  y={converge_point[1]: .3f} {y_unit}"
                plt.circle(converge_point[0],
                           converge_point[1],
                           fill_color=self._POINT_FILL_COLOR,
                           color=self._POINT_COLOR,
                           size=self._CIRCLE_SIZE + 8,
                           alpha=self._POINT_ALPHA,
                           legend_label=legend_label)
            else:
                plt.circle(x_limit,
                           0,
                           fill_color=self._POINT_FILL_COLOR,
                           color=self._POINT_COLOR,
                           size=0,
                           alpha=self._POINT_ALPHA,
                           legend_label='No convergence reached')

            # tol
            # bottom = converge_point[1] - converge_tol/2
            # top = converge_point[1] + converge_tol / 2
            # tol_box = BoxAnnotation(bottom=bottom, top=top, fill_alpha=0.1, fill_color='green')
            # plt.add_layout(tol_box)

            show(plt)
        children = [out]
        super().__init__(children, **kwargs)
