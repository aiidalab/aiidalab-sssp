"""Widgets for the monitoring of processes."""
import traitlets
import ipywidgets as ipw
from IPython.display import clear_output, display
from aiida.orm import ProcessNode, WorkChainNode
from aiida.cmdline.utils.ascii_vis import format_call_graph
from widgets import ProcessOutputFollower

from viewers import viewer


class ProgressBarWidget(ipw.VBox):
    """A bar showing the proggress of a process."""

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, **kwargs):
        self.correspondance = {
            None: (0, 'warning'),
            "created": (0, 'info'),
            "running": (1, 'info'),
            "waiting": (1, 'info'),
            "killed": (2, 'danger'),
            "excepted": (2, 'danger'),
            "finished": (2, 'success'),
        }
        self.bar = ipw.IntProgress(  # pylint: disable=blacklisted-name
            value=0,
            min=0,
            max=2,
            step=1,
            bar_style='warning',  # 'success', 'info', 'warning', 'danger' or ''
            orientation='horizontal',
            layout=ipw.Layout(width="auto"))
        self.state = ipw.HTML(
            description="Calculation state:",
            value='',
            style={'description_width': '100px'},
        )
        super().__init__(children=[self.state, self.bar], **kwargs)

    @traitlets.observe('process')
    def update(self, _=None):
        """Update the bar."""
        self.bar.value, self.bar.bar_style = self.correspondance[
            self.current_state]
        if self.current_state is None:
            self.state.value = 'N/A'
        else:
            self.state.value = self.current_state.capitalize()

    @property
    def current_state(self):
        if self.process is not None:
            return self.process.process_state.value


class ProcessStatusWidget(ipw.VBox):
    """Process status widget"""

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, **kwargs):
        self.progress_bar = ProgressBarWidget()
        self.log_output = ProcessOutputFollower(
            layout=ipw.Layout(min_height='150px', max_height='400px'))
        self.process_id_text = ipw.Text(
            value='',
            description='Process:',
            layout=ipw.Layout(width='auto', flex="1 1 auto"),
            disabled=True,
        )
        ipw.dlink((self, 'process'), (self.process_id_text, 'value'),
                  transform=lambda proc: str(proc))  # pylint: disable=unnecessary-lambda
        ipw.dlink((self, 'process'), (self.log_output, 'process'))
        ipw.dlink((self, 'process'), (self.progress_bar, 'process'))

        super().__init__(children=[
            self.progress_bar,
            self.process_id_text,
            self.log_output,
        ],
                         **kwargs)

    @traitlets.observe('process')
    def _observe_process(self, _):
        self.update()

    def update(self):
        self.progress_bar.update()


class ProcessInputsWidget(ipw.VBox):
    """Widget to select and show process inputs."""

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, process=None, **kwargs):

        self.output = ipw.Output()
        self.info = ipw.HTML()
        self.inputs = ipw.Dropdown(
            options=[('Select input', '')],
            description='Select input:',
            style={'description_width': 'initial'},
            disabled=False,
        )
        self.process = process
        self.update(process)
        self.inputs.observe(self.show_selected_input, names=['value'])
        super().__init__(
            children=[ipw.HBox([self.inputs, self.info]), self.output],
            **kwargs)

    def show_selected_input(self, change=None):
        """Function that displays process inputs selected in the `inputs` Dropdown widget."""
        with self.output:
            self.info.value = ''
            clear_output()
            if change['new']:
                selected_input = self.process.inputs[change['new']]
                self.info.value = "PK: {}".format(selected_input.id)
                display(viewer(selected_input))

    def update(self, process):
        inputs_list = [(l.title(), l)
                        for l in process.outputs] if process else []
        self.inputs.options = [('Select input', '')] + inputs_list

    @traitlets.observe('process')
    def _observe_process(self, change):
        process = change['new']
        self.update(process)


class ProcessOutputsWidget(ipw.VBox):
    """Widget to select and show process outputs."""
    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, process=None, **kwargs):
        self.output = ipw.Output()
        self.info = ipw.HTML()
        self.outputs = ipw.Dropdown(
            options=[('Select output', '')],
            label='Select output',
            description='Select outputs:',
            style={'description_width': 'initial'},
            disabled=False,
        )
        self.process = process
        self.update(process)

        self.outputs.observe(self.show_selected_output, names=['value'])
        super().__init__(
            children=[ipw.HBox([self.outputs, self.info]), self.output],
            **kwargs)

    def show_selected_output(self, change=None):
        """Function that displays process output selected in the `outputs` Dropdown widget."""
        with self.output:
            self.info.value = ''
            clear_output()
            if change['new']:
                selected_output = self.process.outputs[change['new']]
                self.info.value = "PK: {}".format(selected_output.id)
                display(viewer(selected_output))

    def update(self, process):
        outputs_list = [(l.title(), l)
                        for l in process.outputs] if process else []
        self.outputs.options = [('Select output', '')] + outputs_list

    @traitlets.observe('process')
    def _observe_process(self, change):
        process = change['new']
        self.update(process)


class ProcessCallStackWidget(ipw.HTML):
    """Widget that shows process call stack."""
    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self,
                 title="Process Call Stack",
                 path_to_root='../',
                 **kwargs):
        self.title = title
        self.path_to_root = path_to_root
        self.update()
        super().__init__(**kwargs)

    def update(self):
        """Update the call stack that is shown."""
        if self.process is None:
            return
        string = format_call_graph(self.process, info_fn=self.calc_info)
        self.value = string.replace('\n', '<br/>').replace(' ',
                                                           '&nbsp;').replace(
                                                               '#space#', ' ')

    def calc_info(self, node):
        """Return a string with the summary of the state of a CalculationNode."""

        if not isinstance(node, ProcessNode):
            raise TypeError('Unknown type: {}'.format(type(node)))

        process_state = node.process_state.value.capitalize()
        pk = """<a#space#href={0}aiidalab-widgets-base/process.ipynb?id={1}#space#target="_blank">{1}</a>""".format(
            self.path_to_root, node.pk)

        if node.exit_status is not None:
            string = '{}<{}> {} [{}]'.format(node.process_label, pk,
                                             process_state, node.exit_status)
        else:
            string = '{}<{}> {}'.format(node.process_label, pk, process_state)

        if isinstance(node, WorkChainNode) and node.stepper_state_info:
            string += ' [{}]'.format(node.stepper_state_info)
        return string

    @traitlets.observe('process')
    def _observe_process(self, change):
        self.update()


class ProcessLinkWidget(ipw.HTML):
    """A html link to the process show page"""
    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, path_to_root='../', **kwargs):
        self.path_to_root = path_to_root
        self.update()
        super().__init__(**kwargs)

    def update(self):
        """Update the call stack that is shown."""
        if self.process is None:
            return
        if not self.process.is_finished_ok:
            string = 'The process is not finished ok yet.'
            self.value = self._get_html_string(string)
        else:
            pk = """<a#space#href={0}aiidalab-sssp-workflow/check-verification-results.ipynb?id={1}#space#target="_blank">{1}</a>""".format(
                self.path_to_root, self.process.pk)
            string = f'Goto see verification result pk=<{pk}>.'
            self.value = self._get_html_string(string)

    def _get_html_string(self, string):
        return string.replace('\n', '<br/>').replace(' ', '&nbsp;').replace(
            '#space#', ' ')

    @traitlets.observe('process')
    def _observe_process(self, change):
        self.update()
