import warnings

import ipywidgets as ipw
from aiida.orm import Node
from aiidalab_widgets_base.viewers import (
    BandsDataViewer,
    DictViewer,
    FolderDataViewer,
    StructureDataViewer,
)


def viewer(obj, downloadable=True, **kwargs):
    """Display AiiDA data types in Jupyter notebooks.

    :param downloadable: If True, add link/button to download the content of displayed AiiDA object.
    :type downloadable: bool

    Returns the object itself if the viewer wasn't found."""
    if not isinstance(obj, Node):  # only working with AiiDA nodes
        warnings.warn(
            "This viewer works only with AiiDA objects, got {}".format(type(obj))
        )
        return obj

    try:
        _viewer = AIIDA_VIEWER_MAPPING[obj.node_type]
        return _viewer(obj, downloadable=downloadable, **kwargs)
    except (KeyError) as exc:
        if obj.node_type in str(exc):
            warnings.warn(
                "Did not find an appropriate viewer for the {} object. Returning the object "
                "itself.".format(type(obj))
            )
            return obj
        raise exc


class XyDataViewer(ipw.VBox):
    """Viewer class for BandsData object.

    :param bands: XyData object to be viewed
    :type bands: XyData"""

    _PLOT_WIDTH = 900
    _LINE_WIDTH = 2
    _LINE_COLOR = "red"
    _CIRCLE_SIZE = 8
    _RES_COLOR = "red"

    def __init__(self, xydata, **kwargs):
        from bokeh.io import output_notebook, show
        from bokeh.layouts import column
        from bokeh.plotting import figure

        output_notebook(hide_banner=True)
        out = ipw.Output()
        with out:
            # Extract relevant data
            x_data = xydata.get_x()[1]
            x_axis_label = xydata.get_x()[0]
            x_unit = xydata.get_x()[2]

            figure_list = []
            for y in xydata.get_y():
                y_data = y[1]
                y_axis_label = y[0]
                y_unit = y[2]
                # Create the figure
                plot = figure(
                    plot_width=self._PLOT_WIDTH,
                    sizing_mode="stretch_width",
                    x_axis_label=f"{x_axis_label} ({x_unit})",
                    y_axis_label=f"{y_axis_label} ({y_unit})",
                )
                plot.line(
                    x_data,
                    y_data,
                    line_width=self._LINE_WIDTH,
                    line_color=self._LINE_COLOR,
                )  # pylint: disable=too-many-function-args
                plot.square(
                    x_data, y_data, fill_color=self._RES_COLOR, size=self._CIRCLE_SIZE
                )
                figure_list.append(plot)

            show(column(*figure_list))
        children = [out]
        super().__init__(children, **kwargs)


AIIDA_VIEWER_MAPPING = {
    "data.dict.Dict.": DictViewer,
    "data.structure.StructureData.": StructureDataViewer,
    "data.cif.CifData.": StructureDataViewer,
    "data.folder.FolderData.": FolderDataViewer,
    "data.array.bands.BandsData.": BandsDataViewer,
    "data.array.xy.XyData.": XyDataViewer,
}
