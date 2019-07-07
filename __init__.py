from binaryninjaui import DockHandler, DockContextHandler, UIActionHandler, getMonospaceFont
from PySide2 import QtCore
from PySide2.QtCore import Qt
from PySide2.QtWidgets import (QApplication, QHBoxLayout, QVBoxLayout, QLabel, QWidget,
                QPlainTextEdit, QSizePolicy, QFormLayout, QPushButton, QLineEdit)
from PySide2.QtGui import (QFont, QFontMetrics, QTextCursor)

from binaryninja import log_warn, log_info
import subprocess
import os


def addr2line(executable, offset):
    """Returns the line of source like "<file>:<line #>:<function_name>"

    Returns "ERROR: str(exception)" or "?" on failure."""
    addr2line_invocation = "addr2line -e %s -a 0x%x -f" % (executable, offset)
    child = subprocess.Popen(addr2line_invocation.split(),
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    out, err = child.communicate()
    try:
        if not isinstance(out, str):
            out = out.decode()
        output_lines = out.split("\n")
        #output_address = output_lines[0]  # "0x00025ff4"
        function_name = output_lines[1].strip()  # e.g. "png_get_current_pass_number"
        source_line = output_lines[2].strip()  # e.g. "/home/wintermute/targets/libpng-1.6.36/pngtrans.c:861"
    except Exception as e:
        log_warn("[!] Exception encountered in addr2line: %s" % str(e))
        log_warn("    stdout: %s" % out)
        log_warn("    stderr: %s" % err)
        return "ERROR: %s" % str(e)
    if source_line.startswith("??") or source_line.endswith("?"):
        return "?"
    return ":".join((source_line, function_name))

# Module global in case scripting is needed
panes = []
class SourceryPane(QWidget, DockContextHandler):
    def __init__(self, parent, name):
        global panes
        panes.append(self)
        QWidget.__init__(self, parent)
        DockContextHandler.__init__(self, self, name)
        self.actionHandler = UIActionHandler()
        self.actionHandler.setupActionHandler(self)

        # Top: Headers with line info
        header_layout = QFormLayout()
        self.function_info = QLabel("")
        self.line_info = QLabel("")
        header_layout.addRow(self.tr("Function:"), self.function_info)
        header_layout.addRow(self.tr("Line:"), self.line_info)

        # Middle: main source display pane
        textbox_layout = QVBoxLayout()
        self.textbox = QPlainTextEdit()
        self.textbox.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.textbox.setReadOnly(True)
        font = getMonospaceFont(self)
        self.textbox.setFont(font)
        font = QFontMetrics(font)
        self.textbox.setMinimumWidth(40 * font.averageCharWidth())
        self.textbox.setMinimumHeight(30 * font.lineSpacing())
        textbox_layout.addWidget(self.textbox)
        
        # Bottom: buttons for stop/start, and substitution paths
        footer_layout = QVBoxLayout()

        sync_button_layout = QHBoxLayout()
        self.sync_button = QPushButton("Turn Source Sync Off")
        sync_button_layout.addWidget(self.sync_button)

        path_layout = QFormLayout()
        self.original_path = QLineEdit()
        self.substitute_path = QLineEdit()
        self.substitute_path_button = QPushButton("Do Path Substitution")
        path_layout.addRow(self.tr("Original Path:"), self.original_path)
        path_layout.addRow(self.substitute_path_button, self.substitute_path)

        footer_layout.addLayout(sync_button_layout)
        footer_layout.addLayout(path_layout)

        # Putting all the child layouts together
        layout = QVBoxLayout()
        layout.addLayout(header_layout)
        layout.addLayout(textbox_layout)
        layout.addLayout(footer_layout)
        self.setLayout(layout)

        # Set up button signals
        self.substitute_path_button.clicked.connect(self.do_path_substitution)
        self.sync_button.clicked.connect(self.toggle_sync)

        # Actual storage variables
        self.bv = None
        self.filename = None
        self.do_sync = True
        self.path_substitutions = {}
        self.failed_substitutions = []

    def do_path_substitution(self):
        original_path = self.original_path.text()
        new_path = self.substitute_path.text()
        if isinstance(original_path, bytes):
            original_path = original_path.decode()
            new_path = new_path()
        if original_path == "":
            log_warn("Path substitution error: Original path can't be blank")
        elif new_path == "":
            if original_path in self.path_substitutions:
                old_sub = self.path_substitutions.pop(original_path)
                log_info("Removed path substitution: %s -> %s" % (original_path, old_sub))
            else:
                log_warn("Path substitution error: New substitute path can't be blank")
        else:
            self.path_substitutions[original_path] = new_path
            log_info("Added path substitution: %s -> %s" % (original_path, new_path))
            self.failed_substitutions = []  # clear failures when new path added

    def toggle_sync(self):
        if self.do_sync is True:
            self.do_sync = False
            self.sync_button.setText("Turn Source Sync On")
        else:  # self.do_sync is False:
            self.do_sync = True
            self.sync_button.setText("Turn Source Sync Off")

    def set_text(self, text):
        self.textbox.setPlainText(text)

    def set_line(self, text):
        self.line_info.setText(text)
    
    def set_function(self, text):
        self.function_info.setText(text)

    def check_path_substitution(self, path):
        """Checks for files using path substitutions, going from longest to shortest original path"""
        sorted_original_paths = sorted(self.path_substitutions.keys(),
                                       key=lambda k: len(k), reverse=True)
        candidate_matches = []
        for candidate_path in sorted_original_paths:
            if candidate_path in path:
                substitute_pattern = self.path_substitutions[candidate_path]
                substitute_path = path.replace(candidate_path, substitute_pattern)
                candidate_matches.append(substitute_path)
                if os.path.exists(substitute_path):
                    return substitute_path
        # Only log_warn once per file, and only if the user has tried to add translations
        if path not in self.failed_substitutions:
            if len(self.path_substitutions) > 0:
                log_warn("Failed to find substitution for %s" % path)
                path_substitutions = ''
                for orig_path, sub_path in self.path_substitutions.items():
                    path_substitutions += "\n  %s => %s" % (orig_path, sub_path)
                log_warn("Current substitution paths: %s" % path_substitutions)
                failed_candidates = "\n".join(candidate_matches)
                log_warn("Matching patterns' failed substitute paths: %s" % failed_candidates)
            self.failed_substitutions.append(path)
        return ""


    def update_source(self, current_location):
        source_line = addr2line(self.filename, current_location)
        line_number_int = -1
        text = ""
        function_name = ""
        if source_line.startswith("?"):
            line_text = "No source mapping for address 0x%x" % current_location
        elif source_line.startswith("ERROR:"):
            line_text = "%s" % source_line
        else:
            filepath, line_number_str, function_name = source_line.split(":")
            # handle lines like: "16 (discriminator 1)"
            line_number_int = int(line_number_str.split(' ')[0])
            line_text = "%s:%s" % (filepath, line_number_str)
            # Check for the file, then for subsitutions
            if not os.path.exists(filepath):
                new_path = self.check_path_substitution(filepath)
                if new_path == "":
                    self.textbox.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
                    text = '[!] Source file "%s" not found\n' % filepath
                    text += '[*] Associated line info: "%s"' % source_line
                else:
                    filepath = new_path
            # If we still don't have a good path, the text is set to the correct error
            if os.path.exists(filepath):
                self.textbox.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
                with open(filepath, "r") as f:
                    text = f.read()
        self.set_text(text)
        self.set_line(line_text)
        self.set_function(function_name)
        if line_number_int != -1:
            self.set_cursor(line_number_int)
        else:
            self.reset_cursor()

    def reset_cursor(self):
        doc = self.textbox.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        self.textbox.setTextCursor(cursor)

    def set_cursor(self, line_number):
        doc = self.textbox.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        for _ in range(line_number - 1):
            cursor.movePosition(QTextCursor.Down)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        self.textbox.setTextCursor(cursor)
        self.textbox.centerCursor()

    def notifyOffsetChanged(self, offset):
        if self.filename:
            if self.do_sync:
                self.update_source(offset)

    def shouldBeVisible(self, view_frame):
        if view_frame is None:
            return False
        else:
            return True

    def notifyViewChanged(self, view_frame):
        if view_frame is None:
            pass
        else:
            self.bv = view_frame.actionContext().binaryView
            self.filename = self.bv.file.original_filename

    def contextMenuEvent(self, event):
        self.m_contextMenuManager.show(self.m_menu, self.actionHandler)

    @staticmethod
    def create_widget(name, parent, data = None):
        return SourceryPane(parent, name)

def addDynamicDockWidget():
    mw = QApplication.allWidgets()[0].window()
    dock_handler = mw.findChild(DockHandler, '__DockHandler')
    dock_handler.addDockWidget("Sourcery Pane",
    SourceryPane.create_widget, Qt.RightDockWidgetArea, Qt.Vertical, True)

addDynamicDockWidget()
