#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PoC: PyQt6 + QWebEngine + NGL viewer
機能:
 - ローカルPDBを読み込み NGLで表示
 - クリックで原子をピッキング -> Python側に atom info (chain, resno, atomname, serial) を送信
 - Python(Biopython)で resname を変更できるダイアログ
 - 変更後に PDB を書き出し、NGL に再読み込みして更新

注意: 実行環境に PyQt6, PyQt6-WebEngine, biopython が必要
"""

from copy import deepcopy
import sys
import os
from typing import Iterator
from PyQt6 import QtWidgets, QtCore, QtWebEngineWidgets, QtGui
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import pyqtSlot, pyqtSignal, QObject

# from Bio import PDB
# from Bio.PDB import Residue
from io import StringIO
import re
from pdb_file import AdhocPDB, AtomRecord


class Bridge(QObject):
    # signal from python to JS (not strictly required here)
    sendMessage = pyqtSignal(str)

    # signal from JS to python: send JSON string
    jsToPy = pyqtSignal(str)

    @pyqtSlot(str)
    def fromJs(self, s):
        # Called by JS via QWebChannel
        # Emit a Qt signal so main window can connect
        self.jsToPy.emit(s)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NGL + PyQt6 PDB Editor (PoC)")
        self.resize(1200, 800)

        # Central widget split: left = viewer, right = controls
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        hbox = QtWidgets.QHBoxLayout(central)

        # WebEngineView for NGL
        self.view = QtWebEngineWidgets.QWebEngineView()
        html_path = os.path.join(os.path.dirname(__file__), "ngl_viewer.html")
        print("Loading HTML from", html_path)
        self.view.load(QtCore.QUrl.fromLocalFile(html_path))
        hbox.addWidget(self.view, 3)

        # Control panel
        ctrl = QtWidgets.QWidget()
        ctrl_layout = QtWidgets.QVBoxLayout(ctrl)
        hbox.addWidget(ctrl, 1)

        # Buttons and list
        load_btn = QtWidgets.QPushButton("Open PDB")
        load_btn.clicked.connect(self.open_pdb)
        ctrl_layout.addWidget(load_btn)

        self.pdb_label = QtWidgets.QLabel("No file loaded")
        ctrl_layout.addWidget(self.pdb_label)

        self.with_hbond_chk = QtWidgets.QCheckBox("Select with connected hydrogens")
        self.with_hbond_chk.setChecked(False)
        ctrl_layout.addWidget(self.with_hbond_chk)

        self.selected_list = QtWidgets.QListWidget()
        ctrl_layout.addWidget(QtWidgets.QLabel("Selected atoms:"))
        ctrl_layout.addWidget(self.selected_list)

        edit_btn = QtWidgets.QPushButton("Change selected residues' resname...")
        edit_btn.clicked.connect(self.edit_resnames)
        ctrl_layout.addWidget(edit_btn)

        save_btn = QtWidgets.QPushButton("Export PDB (Save)")
        save_btn.clicked.connect(self.export_pdb)
        ctrl_layout.addWidget(save_btn)

        ctrl_layout.addStretch(1)

        # WebChannel bridge
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # connect JS->Py signal
        self.bridge.jsToPy.connect(self.on_js_message)

        # Biopython structures
        self.parser = AdhocPDB()
        self.structure = None
        self.current_pdb_text = None
        self.current_pdb_path = None

        # selected atoms: list of dicts with keys {chain, resno, atomname, serial}
        self.selected_atoms = []

    def open_pdb(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open PDB file", ".", "PDB Files (*.pdb *.ent *.cif);;All Files (*)"
        )
        if not path:
            return
        with open(path, "r") as f:
            pdb_text = f.read()
        self.current_pdb_text = pdb_text
        self.current_pdb_path = path
        self.pdb_label.setText(os.path.basename(path))

        self.parser.load(pdb_text)

        # send pdb text to NGL (JS)
        safe_js = f"loadPDBFromText({repr(pdb_text)})"
        self.view.page().runJavaScript(safe_js)

        # clear selection
        self.selected_atoms.clear()
        self.selected_list.clear()

    @pyqtSlot(str)
    def on_js_message(self, msg):
        # Expecting JSON string from JS with pick info
        import json

        try:
            data = json.loads(msg)
        except Exception as e:
            print("Invalid msg from JS:", msg, e)
            return

        print("Message from JS:", data)

        # Example expected data: {"type":"pick","chain":"A","resno":45,"resname":"GLY","atomname":"CA","serial":123}
        if data.get("type") == "pick":
            entry = {
                "chain": data.get("chain"),
                "resno": int(data.get("resno"))
                if data.get("resno") is not None
                else None,
                "resname": data.get("resname"),
                "atomname": data.get("atomname"),
                "serial": int(data.get("serial"))
                if data.get("serial") is not None
                else None,
            }
            # search entry
            atom: AtomRecord | None = None
            for a in self.parser.get_atoms():
                if a.serial == int(entry["serial"]):  # type: ignore
                    atom = a
                    break

            if atom is None:
                print("Picked atom not found in parser:", entry)
                return

            atoms = [atom]
            if self.with_hbond_chk.isChecked():
                h = self.parser.find_connected_hydrogen(atom)
                atoms.extend(h)

            for a in atoms:
                if a in self.selected_atoms:
                    continue
                self.selected_atoms.append(a)
                self.selected_list.addItem(
                    f"{a.serial} {a.name} {a.resName}{a.resSeq}{a.iCode} chain {a.chainID}"
                )

    def edit_resnames(self):
        if not self.selected_atoms:
            QtWidgets.QMessageBox.information(
                self, "No selection", "Please pick atoms in the viewer first."
            )
            return

        # ask for new resname (3 letters)
        new_res, ok = QtWidgets.QInputDialog.getText(
            self, "New resname", "Enter 3-letter resname (e.g. ALA):"
        )
        if not ok:
            new_res = new_res.strip().upper()
        if len(new_res) != 3:
            QtWidgets.QMessageBox.warning(self, "Invalid", "resname must be 3 letters.")
            return

        new_resname = new_res  # Define new_resname for use below
        changed = []

        sel: AtomRecord
        for sel in self.selected_atoms:
            new_atom: AtomRecord = deepcopy(sel)
            new_atom.resName = new_resname
            # find and update in parser
            self.parser.replace_atom(sel, new_atom)
            changed.append((sel, new_atom))

        new_pdb_text = self.parser.dump()
        self.current_pdb_text = new_pdb_text

        # push updated PDB text back to NGL
        safe_js = f"loadPDBFromText({repr(new_pdb_text)})"
        self.view.page().runJavaScript(safe_js)

        # clear selection
        self.selected_atoms.clear()
        self.selected_list.clear()

    def export_pdb(self):
        if self.current_pdb_text is None:
            QtWidgets.QMessageBox.information(self, "No data", "No PDB loaded.")
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save PDB as", "edited.pdb", "PDB Files (*.pdb);;All Files (*)"
        )
        if not path:
            return
        with open(path, "w") as f:
            f.write(self.parser.dump())
        QtWidgets.QMessageBox.information(self, "Saved", f"Saved to {path}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    # required for QtWebEngine (on some platforms)
    # QtWebEngineWidgets.
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
