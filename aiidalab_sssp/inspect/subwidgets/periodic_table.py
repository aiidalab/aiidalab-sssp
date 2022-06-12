import os
import shutil
import tarfile
from urllib import request

import ipywidgets as ipw
import traitlets
from widget_periodictable import PTableWidget

__all__ = ("PeriodicTable",)


_DB_URL = "https://github.com/unkcpz/sssp-verify-scripts/raw/main/sssp_db.tar.gz"
_DB_FOLDER = "sssp_db"


class PeriodicTable(ipw.VBox):
    """Wrapper-widget for PTableWidget"""

    selected_element = traitlets.Unicode(allow_none=True)

    def __init__(self, cache_folder, **kwargs):
        self._disabled = kwargs.get("disabled", False)
        self._cache_folder = cache_folder

        self.ptable = PTableWidget(states=1, selected_colors=["green"], **kwargs)
        self._last_selected = None
        self.ptable.observe(self._on_element_select)

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

        super().__init__(
            children=(
                self.ptable,
                ipw.HBox(
                    children=[
                        db_update,
                        ipw.HTML(f"The SSSP Database version: {self.db_version}"),
                    ]
                ),
            ),
            layout=kwargs.get("layout", {}),
        )

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
                        element = list(newly_selected)[0]
                        self.ptable.selected_elements = {element: 0}
                        self.selected_element = element
                    else:
                        self.reset()
                    # To have the correct 'last' value for next calls
                    self._last_selected = self.ptable.selected_elements
                else:
                    # first time set: len(event['new']) -> 1
                    self.selected_element = list(event["new"])[0]

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
        elements = []
        for fn in os.listdir(os.path.join(cache_folder, _DB_FOLDER)):
            if "band" not in fn:
                elements.append(fn.split(".")[0])

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
