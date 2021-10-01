"""widget for pseudo inmport"""
import os
import io

import ipywidgets as ipw
import traitlets
from aiidalab_widgets_base.wizard import WizardAppWidgetStep as WizardAppStep
from aiidalab_widgets_base.wizard import WizardAppWidget as WizardApp

from aiida.plugins import DataFactory

UpfData = DataFactory('pseudo.upf')

class InputWidget(ipw.VBox, WizardAppStep):
    """
    Upload a pesudopotential and store it as UpfData in database
    """
    pseudo = traitlets.Instance(UpfData, allow_none=True)
    pseudo_filename = traitlets.Unicode(allow_none=False)
    confirmed_pseudo = traitlets.Instance(UpfData, allow_none=True)

    def __init__(self, description=None, **kwargs):
        self.pseudo_upload_widget = UploadWidget()
        if description is None:
            description = ipw.Label(
                'Select a pseudopotential from one of the following sources and then '
                'click "Confirm" to go to the next step.')
        self.description = description

        self.pseudo_name_text = ipw.Text(
            placeholder='[No pseudo selected]',
            description='Selected:',
            disabled=True,
            layout=ipw.Layout(width='auto'),
        )

        self.confirm_button = ipw.Button(
            description='Confirm',
            tooltip=
            "Confirm the currently selected pseudopotential and go to the next step.",
            button_style='success',
            icon='check-circle',
            disabled=True,
            layout=ipw.Layout(width='auto'),
        )
        self.confirm_button.on_click(self.confirm)

        # Create directional link from the (read-only) 'pseudo_node' traitlet of the
        # pseudo upload widget to our 'pseudo' traitlet:
        ipw.dlink((self.pseudo_upload_widget, 'pseudo'), (self, 'pseudo'))
        ipw.dlink((self.pseudo_upload_widget, 'pseudo_filename'),
                  (self, 'pseudo_filename'))

        super().__init__(children=[
            self.description, self.pseudo_upload_widget, self.pseudo_name_text,
            self.confirm_button
        ],
                         **kwargs)
                         
    @traitlets.default('state')
    def _default_state(self):
        return WizardAppStep.State.READY

    def _update_state(self):
        if self.pseudo is None:
            if self.confirmed_pseudo is None:
                self.state = WizardAppStep.State.READY
            else:
                self.state = WizardAppStep.State.SUCCESS
        else:
            if self.confirmed_pseudo is None:
                self.state = WizardAppStep.State.CONFIGURED
            else:
                self.state = WizardAppStep.State.SUCCESS

    @traitlets.observe('pseudo_filename')
    def _observe_pseudo_filename(self, change):
        pseudo_filename = change['new']
        with self.hold_trait_notifications():
            self.pseudo_name_text.value = pseudo_filename.split('.')[0]

    @traitlets.observe('pseudo')
    def _observe_pseudo(self, change):
        # the first time set the pseudo
        if self.pseudo:
            self.confirm_button.disabled = False

        # after set the new pseudo
        if self.pseudo != change['new']:
            self.confirm_button.disabled = False

    @traitlets.observe('confirmed_pseudo')
    def _observe_confirmed_structure(self, _):
        with self.hold_trait_notifications():
            self._update_state()

    @traitlets.observe('state')
    def _observe_state(self, change):
        with self.hold_trait_notifications():
            state = change['new']
            self.confirm_button.disabled = state != WizardAppStep.State.CONFIGURED

    def confirm(self, _=None):
        self.confirmed_pseudo = self.pseudo
        self.confirm_button.disabled = True 

    def reset(self):  # unconfirm
        self.confirmed_structure = None


class UploadWidget(ipw.VBox):
    """Class that allows to upload pseudopotential from user's computer."""
    pseudo = traitlets.Instance(UpfData, allow_none=True)
    pseudo_filename = traitlets.Unicode(allow_none=False)

    def __init__(self, title='', description="Upload Pseudopotential"):
        self.title = title
        self.file_upload = ipw.FileUpload(description=description,
                                          multiple=False,
                                          layout={'width': 'initial'})
        supported_formats = ipw.HTML(
            """<a href="http://www.quantum-espresso.org/pseudopotentials/
unified-pseudopotential-format" target="_blank">
Supported pseudo formats (Now only support UPF type)
</a>""")
        self.file_upload.observe(self._on_file_upload, names='value')
        super().__init__(children=[self.file_upload, supported_formats])

    def _on_file_upload(self, change=None):
        """When file upload button is pressed."""
        fname, item = next(iter(change['new'].items()))
        try:
            content = item['content']
            self.pseudo = UpfData(io.BytesIO(content))
            self.pseudo_filename = fname
        except ValueError:
            print('wrong pseudopotential file type. (Only UPF support now)')


