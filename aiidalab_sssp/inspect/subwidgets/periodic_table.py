import json
import os
import shutil
import tarfile
from urllib import request

import ipywidgets as ipw
import traitlets
from widget_periodictable import PTableWidget

from aiidalab_sssp.inspect import SSSP_DB

__all__ = ("PeriodicTable",)


_DB_URL = "https://github.com/unkcpz/sssp-verify-scripts/raw/main/sssp_db.tar.gz"
_DB_FOLDER = "sssp_db"


def _load_pseudos(element, db=SSSP_DB) -> dict:
    """Open result json file of element return as dict"""
    if element:
        json_fn = os.path.join(db, f"{element}.json")
        with open(json_fn, "r") as fh:
            pseudos = json.load(fh)

        return {key: pseudos[key] for key in sorted(pseudos.keys(), key=str.lower)}

    return dict()


class PeriodicTable(ipw.VBox):
    """Wrapper-widget for PTableWidget, select the element and update the dict of pseudos"""

    # (output) dict of pseudos for selected element
    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self, cache_folder, **kwargs):
        self._disabled = kwargs.get("disabled", False)
        self._cache_folder = cache_folder

        self.ptable = PTableWidget(states=1, selected_colors=["green"], **kwargs)
        self._last_selected = None
        self.ptable.observe(self._on_element_select)
        self._element = None  # selected element, for record the last selected element

        self.elements = set()  # elements that have json file in the db folder

        # if cache empty run update: first time
        self.db_version = None
        if os.path.exists(os.path.join(cache_folder, _DB_FOLDER)):
            self._update_db(download=False)
        else:
            self._update_db(download=True)

        disable_elements = [
            e for e in self.ptable.allElements if e not in self.elements
        ]
        self.ptable.disabled_elements = disable_elements
        db_update = ipw.Button(
            description="Update Database.",
        )
        db_update.on_click(self._update_db)

        self.json_upload = ipw.FileUpload(
            accept=".json", multiple=False, description="Upload json file"
        )
        self.json_upload.observe(self._on_json_upload, names="value")

        super().__init__(
            children=(
                self.ptable,
                ipw.HBox(
                    children=[
                        db_update,
                        ipw.HTML(f"The SSSP Database version: {self.db_version}"),
                    ]
                ),
                self.json_upload,
            ),
            layout=kwargs.get("layout", {}),
        )

    def _on_json_upload(self, change):
        if change["name"] == "value" and change["type"] == "change":
            if change["new"]:
                # get the first file
                file_name = list(change["new"].keys())[0]
                content = change["new"][file_name]["content"]
                pseudos = json.loads(content.decode("utf-8"))

                # check if the pseudos are valid by check the element name from the key of pseudos
                for key in pseudos:
                    if self._element is not None and self._element not in key:
                        raise ValueError(
                            f"The element name in the json file is not {self._element}, please check the json file."
                        )

                # if self.pseudos is None or len(self.pseudos) == 0:
                #     self.pseudos = pseudos
                # else:
                #     self.pseudos = self.pseudos.update(pseudos)
                self.update_pseudos(element=self._element, pseudos=pseudos)

                # reset the upload widget to empty so that the same file can be uploaded again
                # self.json_upload.value = {}
                self.json_upload._counter = 0

    def _on_element_select(self, event):
        if event["name"] == "selected_elements" and event["type"] == "change":
            if tuple(event["new"].keys()) == ("Du",):
                self._last_selected = event["old"]
            elif tuple(event["old"].keys()) == ("Du",):
                if len(event["new"]) != 1:
                    # Reset to only one element only if there is more than one selected,
                    # to avoid infinite loops
                    newly_selected = set(event["new"]).difference(self._last_selected)
                    # If this is empty it's ok, unselect all
                    # If there is more than one, that's weird... to avoid problems, anyway, I pick one of the two
                    if newly_selected:
                        self._element = list(newly_selected)[0]
                        self.ptable.selected_elements = {self._element: 0}
                        self.update_pseudos(self._element)
                    else:
                        self.reset()
                    # To have the correct 'last' value for next calls
                    self._last_selected = self.ptable.selected_elements
                else:
                    # first time set: len(event['new']) -> 1
                    self._element = list(event["new"])[0]
                    self.update_pseudos(self._element)

    def update_pseudos(self, element=None, pseudos=None):
        pseudos = {} if pseudos is None else pseudos
        if element is not None:
            pseudos.update(_load_pseudos(element))

        self.pseudos = pseudos

    def _update_db(self, _=None, download=True):
        """update cached db fetch from remote. and update ptable"""
        # download from remote
        if download:
            self._download(self._cache_folder)

        self.elements = self._get_enabled_elements(self._cache_folder)
        disable_elements = [
            e for e in self.ptable.allElements if e not in self.elements
        ]
        self.ptable.disabled_elements = disable_elements
        self.db_version = self._get_db_version(self._cache_folder)

        self.reset()

    @staticmethod
    def _get_enabled_elements(cache_folder):
        elements = set()
        for fn in os.listdir(os.path.join(cache_folder, _DB_FOLDER)):
            if "band" not in fn:
                elements.add(fn.split(".")[0])

        return elements

    @staticmethod
    def _get_db_version(cache_folder):
        with open(os.path.join(cache_folder, _DB_FOLDER, "version.txt"), "r") as fh:
            lines = fh.read()
            db_version = lines.split("\n")[0].split("=")[1].strip()

        return db_version

    @staticmethod
    def _download(cache_folder):
        """
        The original sssp_db folder is deleted and re-downloaded from
        source and extracted.

        :params cache_folder: folder where cache stored
        """
        # Purge whole db folder filst
        db_dir = f"{cache_folder}/sssp_db"
        if os.path.exists(db_dir) and os.path.isdir(db_dir):
            shutil.rmtree(db_dir)

        # download DB tar file from source
        tar_file = f"{cache_folder}/sssp_db.tar.gz"
        request.urlretrieve(_DB_URL, tar_file)

        # decompress to the db folder
        tar = tarfile.open(tar_file)
        os.chdir(cache_folder)
        tar.extractall()
        tar.close()

        os.remove(tar_file)

    @property
    def value(self) -> dict:
        """Return value for wrapped PTableWidget"""

        return self.ptable.selected_elements.copy()

    @property
    def disabled(self) -> None:
        """Disable widget"""
        return self._disabled

    @disabled.setter
    def disabled(self, value: bool) -> None:
        """Disable widget"""
        if not isinstance(value, bool):
            raise TypeError("disabled must be a boolean")

    def reset(self):
        """Reset widget"""
        self.ptable.selected_elements = {}
        self.selected_element = None

    def freeze(self):
        """Disable widget"""
        self.disabled = True

    def unfreeze(self):
        """Activate widget (in its current state)"""
        self.disabled = False
