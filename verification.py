"""Widget for delta factor calculation"""
import ipywidgets as ipw
import traitlets
import numpy as np
import re

from aiidalab_widgets_base.wizard import WizardAppWidgetStep as WizardAppStep
from aiidalab_widgets_base import CodeDropdown

from aiida.plugins import DataFactory, WorkflowFactory
from aiida import orm

UpfData = DataFactory('pseudo.upf')

class VerificationWidget(ipw.VBox, WizardAppStep):
    """ComputeDeltaFactorWidget"""

    process = traitlets.Instance(orm.ProcessNode, allow_none=True)
    input_pseudo = traitlets.Instance(UpfData, allow_none=True)

    skip = False

    def __init__(self, **kwargs):
        pw_code = CodeDropdown(input_plugin='quantumespresso.pw',
                               description="PW code")
        self.ph_code = CodeDropdown(input_plugin='quantumespresso.ph',
                               description="PH code",
                               layout={"visibility": "hidden"})

        self.code_group = ipw.VBox(children=[pw_code, self.ph_code])

        protocol_list = ['efficiency', 'precision', 'test'] # will read from sssp plugin
        properties_list = ['Delta factor', 'Convergence: Cohesive Energy',
            'Convergence: Bands Distance', 'Convergence: Pressure']

        phonon_checkbox = ipw.Checkbox(value=False, description='Convergence: Phonon Frequencies')
        phonon_checkbox.observe(self.on_phonon_checkbox_change, names="value")

        self.properties = [ipw.Checkbox(value=False, description=label) for label in properties_list] + [phonon_checkbox]

        option_box_extra = {
            'style': {
                'description_width': '120px'
            },
            'layout': {
                'max_width': '210px'
            }
        }

        self.protocol = ipw.Dropdown(
            options=protocol_list,
            value='efficiency',
            description='Protocol:',
            disabled=False,
            **option_box_extra)

        self.dual= ipw.BoundedIntText(
            value=8,
            step=1,
            min=1,
            description="# dual",
            **option_box_extra)

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

        # the settings for protocol choose (dropdown) and properties (checkboxes) and infos for query
        self.settings = ipw.HBox(children=[
            ipw.VBox(
                children=self.properties,
            ),
            ipw.VBox(
                children=[
                    self.protocol,
                    self.dual,
                ],
            ),
            ipw.VBox(
                children=[
                    self.query_pp_element,
                    self.query_pp_type,
                    self.query_pp_family,
                    self.query_pp_version,
                ],
            ),
        ])

        self.number_of_nodes = ipw.BoundedIntText(
            value=1, step=1, min=1,
            description="# nodes",
            disabled=False,
            **option_box_extra)
        self.cpus_per_node = ipw.BoundedIntText(
            value=1, step=1, min=1,
            description="# cpus per node",
            **option_box_extra)
        self.total_num_cpus = ipw.BoundedIntText(
            value=1, step=1, min=1,
            description="# total cpus",
            disabled=True,
            **option_box_extra)

        # Update the total # of CPUs int text:
        self.number_of_nodes.observe(self._update_total_num_cpus, 'value')
        self.cpus_per_node.observe(self._update_total_num_cpus, 'value')

        resource_selection_prompt = ipw.HTML(
            "Select the compute resources for this calculation.")
        resource_selection_help = ipw.HTML("""<div style="line-height:120%; padding-top:25px;">
            <p>There is no general rule of thumb on how to select the appropriate number of
            nodes and cores. In general:</p>
            <ul>
            <li>Increase the number of nodes if you run out of memory for larger structures.</li>
            <li>Increase the number of nodes and cores if you want to reduce the total runtime.</li>
            </ul>
            <p>However, specifying the optimal configuration of resources is a complex issue and
            simply increasing either cores or nodes may not have the desired effect.</p></div>""")
        self.resources = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    resource_selection_prompt,
                    self.number_of_nodes,
                    self.cpus_per_node,
                    self.total_num_cpus,
                ],
                layout=ipw.Layout(min_width='310px'),
            ),
            resource_selection_help,
        ])


        # Clicking on the 'verify' button will trigger the execution of the
        # verify() method.
        self.verify_button = ipw.Button(
            description='Verify',
            tooltip="Submit the calculation with the selected parameters.",
            icon='play',
            button_style='success',
            layout=ipw.Layout(width='auto', flex="1 1 auto"),
            disabled=False)
        self.verify_button.on_click(self._on_verify_button_clicked)

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
            children=[self.verify_button, self.skip_button])

        self.config_tabs = ipw.Tab(
            children=[self.settings, self.code_group, self.resources],
            layout=ipw.Layout(height='240px'),
        )
        self.config_tabs.set_title(0, 'Verification Setting')
        self.config_tabs.set_title(1, 'Codes Setting')
        self.config_tabs.set_title(2, 'Compute Resources Setting')

        description = ipw.Label(
            'Specify the parameters and options for the calculation and then click on "Verify".'
        )

        super().__init__(
            children=[description, self.config_tabs, self.buttons], **kwargs)

    def on_phonon_checkbox_change(self, change):
        """If phonon checkbox is clicked."""
        if change['new']:
            self.ph_code.layout.visibility = "visible"
        else:
            self.ph_code.layout.visibility = "hidden"

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

    def _on_verify_button_clicked(self, _):
        self.verify()

    def verify(self):
        """Run the workflow to calculate delta factor"""
        DeltaFactorWorkChain = WorkflowFactory('sssp_workflow.delta_factor')

        if self.input_pseudo is None:
            print('Please set input pseudopotential in previous step.')
        else:
            from aiida.engine import submit

            builder = DeltaFactorWorkChain.get_builder()

            builder.pseudo = self.input_pseudo
            builder.code = self.code_group.children[0].selected_code
            # builder.ph_code = self.code_group.children[1].selected_code

            builder.protocol = orm.Str(self.protocol.value)
            builder.dual = orm.Float(self.dual.value)

            builder.options = orm.Dict(dict=self.options)
            builder.clean_workdir = orm.Bool(True)

            self.verify_button.disabled = True

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