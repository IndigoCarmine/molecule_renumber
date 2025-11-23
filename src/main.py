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


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)


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
        html_path = get_resource_path("ngl_viewer.html")
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

        self.select_between_btn = QtWidgets.QPushButton("Select atoms between (2 atoms)")
        self.select_between_btn.setEnabled(False)
        self.select_between_btn.clicked.connect(self.select_atoms_between)
        ctrl_layout.addWidget(self.select_between_btn)

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

    def update_button_state(self):
        self.select_between_btn.setEnabled(len(self.selected_atoms) == 2)

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
        self.update_button_state()
        self.update_ngl_selection()

    def update_ngl_selection(self):
        import json
        
        if not self.selected_atoms:
            # clear highlight - send empty serials array
            data = {"serials": []}
            safe_js = f"highlightAtoms({json.dumps(data)})"
            self.view.page().runJavaScript(safe_js)
            return

        # collect serial numbers
        serials = [a.serial for a in self.selected_atoms]
        if not serials:
            data = {"serials": []}
            safe_js = f"highlightAtoms({json.dumps(data)})"
            self.view.page().runJavaScript(safe_js)
            return

        # Send JSON data to JavaScript
        data = {"serials": serials}
        
        print(f"Updating NGL selection with serials: {serials}")
        safe_js = f"highlightAtoms({json.dumps(data)})"
        self.view.page().runJavaScript(safe_js)

    @pyqtSlot(str)
    def on_js_message(self, msg):
        # Expecting JSON string from JS with pick info
        import json

        try:
            data = json.loads(msg)
        except Exception as e:
            print("Invalid msg from JS:", msg, e)
            return

        # Handle different message types from JavaScript
        msg_type = data.get("type")
        
        if msg_type == "log":
            # Log message from JavaScript
            log_msg = data.get("message", "")
            log_data = data.get("data", {})
            print(f"[JS Log] {log_msg}", log_data if log_data else "")
            return
        
        if msg_type == "pick":
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

            # Check if the clicked atom is already selected
            # If so, we toggle OFF (remove) all related atoms (clicked + hydrogens)
            # If not, we toggle ON (add) them
            
            # We determine "already selected" by checking if the *primary clicked atom* is in the list.
            # (Alternatively, we could check if *any* of the atoms are in the list, but checking the clicked one is more intuitive for "toggle")
            is_toggle_off = (atom in self.selected_atoms)

            if is_toggle_off:
                # Remove atoms
                for a in atoms:
                    if a in self.selected_atoms:
                        # Remove from internal list
                        self.selected_atoms.remove(a)
                        
                        # Remove from UI list
                        # We need to find the matching QListWidgetItem
                        # The text format is: f"{a.serial} {a.name} {a.resName}{a.resSeq}{a.iCode} chain {a.chainID}"
                        # It's safer/easier to just rebuild the list or search by text. 
                        # Given the list size is likely small, rebuilding might be okay, but let's try to find and remove.
                        search_text = f"{a.serial} {a.name} {a.resName}{a.resSeq}{a.iCode} chain {a.chainID}"
                        items = self.selected_list.findItems(search_text, QtCore.Qt.MatchFlag.MatchExactly)
                        for item in items:
                            row = self.selected_list.row(item)
                            self.selected_list.takeItem(row)
            else:
                # Add atoms
                for a in atoms:
                    if a in self.selected_atoms:
                        continue
                    self.selected_atoms.append(a)
                    self.selected_list.addItem(
                        f"{a.serial} {a.name} {a.resName}{a.resSeq}{a.iCode} chain {a.chainID}"
                    )
            
            self.update_button_state()
            self.update_ngl_selection()

    def select_atoms_between(self):
        if len(self.selected_atoms) != 2:
            return
        
        atom1 = self.selected_atoms[0]
        atom2 = self.selected_atoms[1]
        
        path_atoms = self.parser.find_atoms_between(atom1, atom2)
        
        # If "Select with connected hydrogens" is checked, add hydrogens for path atoms
        final_atoms = list(path_atoms)
        if self.with_hbond_chk.isChecked():
            for atom in path_atoms:
                hydrogens = self.parser.find_connected_hydrogen(atom)
                for h in hydrogens:
                    if h not in final_atoms:
                        final_atoms.append(h)

        # Add new atoms to selection
        for a in final_atoms:
            if a not in self.selected_atoms:
                self.selected_atoms.append(a)
                self.selected_list.addItem(
                    f"{a.serial} {a.name} {a.resName}{a.resSeq}{a.iCode} chain {a.chainID}"
                )
        
        self.update_button_state()
        self.update_ngl_selection()

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
        self.update_button_state()
        self.update_ngl_selection()

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
