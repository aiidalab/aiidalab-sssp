"""Widget for delta factor calculation"""
import ipywidgets as ipw
import traitlets
import numpy as np
import re

from aiidalab_widgets_base import CodeDropdown

from aiida.plugins import DataFactory, WorkflowFactory
from aiida.engine import submit
from aiida import orm

UpfData = DataFactory('upf')


class ComputeVerificationWidget(ipw.VBox):
    """ComputeDeltaFactorWidget"""

    process = traitlets.Instance(orm.ProcessNode, allow_none=True)
    input_pseudo = traitlets.Instance(UpfData, allow_none=True)

    skip = False

    def __init__(self, **kwargs):
        setup_pw_code_params = {
            "computer": "localhost",
            "description": "pw.x in AiiDAlab container.",
            "label": "pw",
            "input_plugin": "quantumespresso.pw",
            'remote_abs_path': '/usr/bin/pw.x',
        }
        setup_ph_code_params = {
            "computer": "localhost",
            "description": "ph.x in AiiDAlab container.",
            "label": "ph",
            "input_plugin": "quantumespresso.ph",
            'remote_abs_path': '/usr/bin/ph.x',
        }


        pw_code = CodeDropdown(input_plugin='quantumespresso.pw',
                               description="Pw code",
                               setup_code_params=setup_pw_code_params)
        ph_code = CodeDropdown(input_plugin='quantumespresso.ph',
                               description="Ph code",
                               setup_code_params=setup_ph_code_params)

        self.code_group = ipw.VBox(children=[pw_code, ph_code])

        parameters_setting_prompt = ipw.HTML(
            "Select the compute parameters for this calculation.")
        parameters_setting_help = ipw.HTML(
            """<p>Converge on [30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 120, 150, 200]</p>

<p><a href="https://raw.githubusercontent.com/unkcpz/aiida-sssp-workflow
/develop/aiida_sssp_workflow/workflows/protocol.yml" target="_blank">
protocol.yml
</a></p>""")

        extra = {
            'style': {
                'description_width': '150px'
            },
            'layout': {
                'max_width': '1000px'
            }
        }

        self.protocol = ipw.Dropdown(
            options=['efficiency', 'precision'],
            value='efficiency',
            description='Protocol:',
            disabled=False,
            **extra)
        self.dual= ipw.BoundedIntText(
            value=8,
            step=1,
            min=1,
            description="# dual",
            **extra)

        # set the parameters for delta factor calculation
        self.parameters = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    parameters_setting_prompt,
                    self.protocol,
                    self.dual,
                ],
                layout=ipw.Layout(min_width='310px'),
            ),
            parameters_setting_help,
        ])

        extra = {
            'style': {
                'description_width': '150px'
            },
            'layout': {
                'max_width': '240px'
            }
        }

        self.number_of_nodes = ipw.BoundedIntText(value=1,
                                                  step=1,
                                                  min=1,
                                                  description="# nodes",
                                                  disabled=False,
                                                  **extra)
        self.cpus_per_node = ipw.BoundedIntText(value=1,
                                                step=1,
                                                min=1,
                                                description="# cpus per node",
                                                **extra)
        self.total_num_cpus = ipw.BoundedIntText(value=1,
                                                 step=1,
                                                 min=1,
                                                 description="# total cpus",
                                                 disabled=True,
                                                 **extra)
        self.max_wallclock_seconds = ipw.BoundedIntText(
            value=3600,
            step=1,
            min=1,
            max=36000,
            description="# max wallclock seconds",
            disabled=False,
            **extra)

        # Update the total # of CPUs int text:
        self.number_of_nodes.observe(self._update_total_num_cpus, 'value')
        self.cpus_per_node.observe(self._update_total_num_cpus, 'value')

        resource_selection_prompt = ipw.HTML(
            "Select the compute resources for this calculation.")
        resource_selection_help = ipw.HTML(
            """<div style="line-height:120%; padding-top:25px;">
            <p>There is no general rule of thumb on how to select the appropriate number of
            nodes and cores. In general:</p>
            <ul>
            <li>Increase the number of nodes if you run out of memory for larger structures.</li>
            <li>Increase the number of nodes and cores if you want to reduce the total runtime.</li>
            </ul>
            <p>However, specifying the optimal configuration of resources is a complex issue and
            simply increasing either cores or nodes may not have the desired effect.</p></div>"""
        )
        self.resources = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    resource_selection_prompt,
                    self.number_of_nodes,
                    self.cpus_per_node,
                    self.max_wallclock_seconds,
                    self.total_num_cpus,
                ],
                layout=ipw.Layout(min_width='360px'),
            ),
            resource_selection_help,
        ])

        self.query_pp_element = ipw.Text(
            value='Unknown',
            placeholder='The element of the pseudo',
            description='Element:',
            disabled=False
        )
        self.query_pp_type = ipw.Text(
            value='Unknown',
            placeholder='The type of the pseudo',
            description='PP type:',
            disabled=False
        )
        self.query_pp_family = ipw.Text(
            value='UnKnown',
            placeholder='The family name of the pseudo',
            description='Family name:',
            disabled=False
        )
        self.query_pp_version = ipw.Text(
            value='UnKnown',
            placeholder='The version number of the pseudo',
            description='Version:',
            disabled=False
        )

        store_info_help = ipw.HTML(
            """<div style="line-height:120%; padding-top:25px;">
            <p>For easily query the information, give the specific name attributes to the calculation:</p>
            <ul>
            <li>Increase the number of nodes if you run out of memory for larger structures.</li>
            <li>Increase the number of nodes and cores if you want to reduce the total runtime.</li>
            </ul>
            </div>"""
        )
        self.store_setting = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    self.query_pp_element,
                    self.query_pp_type,
                    self.query_pp_family,
                    self.query_pp_version,
                ],
                layout=ipw.Layout(min_width='360px'),
            ),
            store_info_help,
        ])

        # Clicking on the 'submit' button will trigger the execution of the
        # submit() method.
        self.submit_button = ipw.Button(
            description='Submit',
            tooltip="Submit the calculation with the selected parameters.",
            icon='play',
            button_style='success',
            layout=ipw.Layout(width='auto', flex="1 1 auto"),
            disabled=False)
        self.submit_button.on_click(self._on_submit_button_clicked)

        # The 'skip' button is only shown when the skip() method is implemented.
        self.skip_button = ipw.Button(description='Skip',
                                      icon='fast-forward',
                                      button_style='info',
                                      layout=ipw.Layout(width='auto',
                                                        flex="1 1 auto"),
                                      disabled=True)
        if self.skip:  # skip() method is implemented
            # connect with skip_button
            self.skip_button.on_click(self.skip)  # connect with skip_button
        else:  # skip() not implemented
            # hide the button
            self.skip_button.layout.visibility = 'hidden'

        # Place all buttons at the footer of the widget.
        self.buttons = ipw.HBox(
            children=[self.submit_button, self.skip_button])

        self.config_tabs = ipw.Tab(
            children=[self.code_group, self.parameters, self.resources, self.store_setting],
            layout=ipw.Layout(height='240px'),
        )
        self.config_tabs.set_title(0, 'Code')
        self.config_tabs.set_title(1, 'Protocol')
        self.config_tabs.set_title(2, 'Compute resources')
        self.config_tabs.set_title(3, 'Query info setting')

        description = ipw.Label(
            'Specify the parameters and options for the calculation and then click on "Submit".'
        )

        super().__init__(
            children=[description, self.config_tabs, self.buttons], **kwargs)

    @traitlets.observe('input_pseudo')
    def _observe_input_pseudo(self, change):
        if change['new']:
            upf_content = change['new'].get_content()
            element = parse_element(upf_content)
            pp_type = parse_pp_type(upf_content)

            self.query_pp_element.value = element
            self.query_pp_type.value = pp_type

            # set dual upon pp type
            if pp_type == 'NC':
                self.dual.value = 4
            else:
                self.dual.value = 8

    def _update_total_num_cpus(self, _):
        self.total_num_cpus.value = self.number_of_nodes.value * self.cpus_per_node.value

    def _on_submit_button_clicked(self, _):
        self.submit()

    def submit(self):
        """Run the workflow to calculate delta factor"""
        if self.input_pseudo is None:
            print('Please set input pseudopotential in previous step.')
        else:
            builder = WorkflowFactory(
                'sssp_workflow.verification').get_builder()

            builder.pseudo = self.input_pseudo
            builder.pw_code = self.code_group.children[0].selected_code
            builder.ph_code = self.code_group.children[1].selected_code

            builder.protocol = orm.Str(self.protocol.value)

            ecutwfc = np.array(
                [30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100, 120, 150, 200])
            ecutrho = ecutwfc * self.dual.value
            builder.parameters.ecutwfc_list = orm.List(list=list(ecutwfc))
            builder.parameters.ecutrho_list = orm.List(list=list(ecutrho))

            builder.options = orm.Dict(dict=self.options)
            builder.clean_workdir = orm.Bool(True)

            self.submit_button.disabled = True

            # print(builder)
            self.process = submit(builder)

            # set extras for easy query and comprehensive show results
            extras = {
                'element': self.query_pp_element.value,
                'pp_type': self.query_pp_type.value,
                'pp_family': self.query_pp_family.value,
                'pp_version': self.query_pp_version.value,
                'pp_filename': self.input_pseudo.filename,
            }
            self.process.set_extra_many(extras)

    @property
    def options(self):
        return {
            'max_wallclock_seconds': self.max_wallclock_seconds.value,
            'resources': {
                'num_machines': self.number_of_nodes.value,
                'num_mpiprocs_per_machine': self.cpus_per_node.value
            }
        }


REGEX_ELEMENT_V1 = re.compile(r"""(?P<element>[a-zA-Z]{1,2})\s+Element""")
REGEX_ELEMENT_V2 = re.compile(r"""\s*element\s*=\s*['"]\s*(?P<element>[a-zA-Z]{1,2})\s*['"].*""")

REGEX_PP_TYPE_V1 = re.compile(r"""(?P<pp_type>[a-zA-Z]{1,2})\s+Ultrasoft pseudopotential""")
REGEX_PP_TYPE_V2 = re.compile(r"""\s*pseudo_type\s*=\s*['"]\s*(?P<pp_type>[a-zA-Z]{1,2})\s*['"].*""")

def parse_element(content: str):
    """Parse the content of the UPF file to determine the element.
    :param stream: a filelike object with the binary content of the file.
    :return: the symbol of the element following the IUPAC naming standard.
    """
    for regex in [REGEX_ELEMENT_V2, REGEX_ELEMENT_V1]:

        match = regex.search(content)

        if match:
            return match.group('element')

    raise ValueError(f'could not parse the element from the UPF content: {content}')

def parse_pp_type(content: str):
    """Parse the content of the UPF file to determine the element.
    :param stream: a filelike object with the binary content of the file.
    :return: the symbol of the element following the IUPAC naming standard.
    """
    for regex in [REGEX_PP_TYPE_V2, REGEX_PP_TYPE_V1]:

        match = regex.search(content)

        if match:
            return match.group('pp_type')

    raise ValueError(f'could not parse the pp_type from the UPF content: {content}')