import sys
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QHBoxLayout, QProgressBar,
    QDialog, QTextEdit, QCheckBox, QLabel, QStackedWidget,
    QSplitter
)
from PySide6.QtCore import Qt, QPropertyAnimation, QRect, QSize
from PySide6.QtGui import QPixmap

from metadata_cleaner import (
    clean_file, get_file_type,
    extract_metadata, compare_metadata
)
from logger import log, get_log, clear_log


DARK_STYLESHEET = """
QWidget {
    background-color: #1e1e1e;
    color: #dddddd;
    font-family: Segoe UI, sans-serif;
    font-size: 10pt;
}
QPushButton {
    background-color: #333333;
    border: 1px solid #555555;
    padding: 6px 10px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #444444;
}
QPushButton#themeButton {
    background-color: transparent;
    border: none;
    font-size: 14pt;
    padding: 2px;
}
QTableWidget {
    background-color: #2a2a2a;
    gridline-color: #444444;
}
QHeaderView::section {
    background-color: #3a3a3a;
    color: #dddddd;
    padding: 4px;
    border: none;
}
QProgressBar {
    background-color: #333333;
    border: 1px solid #555555;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #0078d4;
}
QTextEdit {
    background-color: #2a2a2a;
    border: 1px solid #555555;
}
#previewPanel {
    border: 1px solid #555555;
    border-radius: 6px;
}
"""

LIGHT_STYLESHEET = """
QWidget {
    background-color: #f0f0f0;
    color: #000000;
    font-family: Segoe UI, sans-serif;
    font-size: 10pt;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    padding: 6px 10px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #e6e6e6;
}
QPushButton#themeButton {
    background-color: transparent;
    border: none;
    font-size: 14pt;
    padding: 2px;
}
QTableWidget {
    background-color: #ffffff;
    gridline-color: #cccccc;
}
QHeaderView::section {
    background-color: #e0e0e0;
    color: #000000;
    padding: 4px;
    border: none;
}
QProgressBar {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #0078d4;
}
QTextEdit {
    background-color: #ffffff;
    border: 1px solid #cccccc;
}
#previewPanel {
    border: 1px solid #cccccc;
    border-radius: 6px;
}
"""


class MetadataDialog(QDialog):
    def __init__(self, metadata: dict, title="Metadata Viewer", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        layout = QVBoxLayout()
        text = QTextEdit()
        text.setReadOnly(True)

        if metadata:
            formatted = "<br>".join(f"<b>{k}:</b> {v}" for k, v in metadata.items())
        else:
            formatted = "No metadata found."

        text.setHtml(formatted)
        layout.addWidget(text)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.setLayout(layout)


class LogWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log")

        layout = QVBoxLayout()
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.clear_btn = QPushButton("Clear")
        self.save_btn = QPushButton("Save to file")

        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.clear_btn)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

        self.refresh_btn.clicked.connect(self.refresh)
        self.clear_btn.clicked.connect(self.clear_log)
        self.save_btn.clicked.connect(self.save_log)

        self.refresh()

    def refresh(self):
        self.text.setPlainText(get_log())

    def clear_log(self):
        clear_log()
        self.refresh()

    def save_log(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save log", "log.txt", "Text Files (*.txt)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(get_log())
            QMessageBox.information(self, "Saved", "Log saved successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save log: {e}")


class SettingsWindow(QDialog):
    def __init__(
        self,
        overwrite_files: bool,
        show_removed_dialog: bool,
        confirm_overwrite: bool,
        auto_open_folder: bool,
        rules: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Settings")

        self._rules = rules.copy()

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Output options:"))
        self.output_overwrite = QCheckBox(
            "Overwrite original files instead of creating _cleaned copies"
        )
        self.output_overwrite.setChecked(overwrite_files)
        layout.addWidget(self.output_overwrite)

        self.confirm_overwrite = QCheckBox(
            "Ask for confirmation before overwriting originals"
        )
        self.confirm_overwrite.setChecked(confirm_overwrite)
        layout.addWidget(self.confirm_overwrite)

        layout.addWidget(QLabel("Post-processing:"))
        self.show_removed_dialog = QCheckBox(
            "Show 'Metadata Removed' dialog after cleaning"
        )
        self.show_removed_dialog.setChecked(show_removed_dialog)
        layout.addWidget(self.show_removed_dialog)

        self.auto_open_folder = QCheckBox(
            "Open output folder after cleaning finishes"
        )
        self.auto_open_folder.setChecked(auto_open_folder)
        layout.addWidget(self.auto_open_folder)

        layout.addSpacing(10)
        layout.addWidget(QLabel("Power User: Metadata Rules"))

        self.remove_gps_cb = QCheckBox("Remove GPS/location metadata")
        self.remove_gps_cb.setChecked(self._rules.get("remove_gps", True))
        layout.addWidget(self.remove_gps_cb)

        self.remove_ts_cb = QCheckBox("Remove timestamps (DateTime, DateTimeOriginal, CreateDate)")
        self.remove_ts_cb.setChecked(self._rules.get("remove_timestamps", True))
        layout.addWidget(self.remove_ts_cb)

        self.remove_cam_cb = QCheckBox("Remove camera info (Make, Model, Lens)")
        self.remove_cam_cb.setChecked(self._rules.get("remove_camera", True))
        layout.addWidget(self.remove_cam_cb)

        self.remove_xmp_cb = QCheckBox("Remove XMP metadata")
        self.remove_xmp_cb.setChecked(self._rules.get("remove_xmp", True))
        layout.addWidget(self.remove_xmp_cb)

        self.remove_iptc_cb = QCheckBox("Remove IPTC metadata")
        self.remove_iptc_cb.setChecked(self._rules.get("remove_iptc", True))
        layout.addWidget(self.remove_iptc_cb)

        self.keep_icc_cb = QCheckBox("Keep ICC color profile")
        self.keep_icc_cb.setChecked(self._rules.get("keep_icc", True))
        layout.addWidget(self.keep_icc_cb)

        self.keep_orientation_cb = QCheckBox("Keep orientation tag")
        self.keep_orientation_cb.setChecked(self._rules.get("keep_orientation", True))
        layout.addWidget(self.keep_orientation_cb)

        layout.addSpacing(10)
        layout.addWidget(QLabel("More tweaks can be added here later."))

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        layout.addWidget(save_btn)

        self.setLayout(layout)

    def get_settings(self):
        rules = {
            "remove_gps": self.remove_gps_cb.isChecked(),
            "remove_timestamps": self.remove_ts_cb.isChecked(),
            "remove_camera": self.remove_cam_cb.isChecked(),
            "remove_xmp": self.remove_xmp_cb.isChecked(),
            "remove_iptc": self.remove_iptc_cb.isChecked(),
            "keep_icc": self.keep_icc_cb.isChecked(),
            "keep_orientation": self.keep_orientation_cb.isChecked(),
        }
        return {
            "overwrite_files": self.output_overwrite.isChecked(),
            "confirm_overwrite": self.confirm_overwrite.isChecked(),
            "show_removed_dialog": self.show_removed_dialog.isChecked(),
            "auto_open_folder": self.auto_open_folder.isChecked(),
            "rules": rules,
        }


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewPanel")

        self._original_pixmap: QPixmap | None = None

        layout = QVBoxLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.title_label = QLabel("Preview")
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.stack = QStackedWidget()

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(QSize(150, 120))
        self.image_label.setScaledContents(False)

        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)

        self.empty_label = QLabel("No preview available")
        self.empty_label.setAlignment(Qt.AlignCenter)

        self.stack.addWidget(self.image_label)
        self.stack.addWidget(self.text_preview)
        self.stack.addWidget(self.empty_label)

        layout.addWidget(self.title_label)
        layout.addWidget(self.stack)
        self.setLayout(layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.stack.currentWidget() is self.image_label:
            self._scale_pixmap()

    def _scale_pixmap(self):
        if not self._original_pixmap:
            return
        size = self.image_label.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = self._original_pixmap.scaled(
            size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)

    def show_preview(self, path: str, file_type: str):
        self.title_label.setText(f"Preview — {Path(path).name}")
        if file_type == "image":
            self._show_image(path)
        elif file_type in ("pdf", "media", "other"):
            self._show_text_summary(path, file_type)
        else:
            self._show_empty()

    def _show_image(self, path: str):
        pix = QPixmap(path)
        if pix.isNull():
            log(f"Failed to load image preview for {path}")
            self._show_text_summary(path, "image")
            return
        self._original_pixmap = pix
        self.stack.setCurrentWidget(self.image_label)
        self._scale_pixmap()

    def _show_text_summary(self, path: str, file_type: str):
        self._original_pixmap = None
        info = [
            f"File: {Path(path).name}",
            f"Type: {file_type}",
            f"Path: {path}",
        ]
        self.text_preview.setPlainText("\n".join(info))
        self.stack.setCurrentWidget(self.text_preview)

    def _show_empty(self):
        self._original_pixmap = None
        self.stack.setCurrentWidget(self.empty_label)
        self.title_label.setText("Preview")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Metadata Cleaner for Windows")
        self.resize(1000, 650)

        self.current_theme = "dark"
        self.overwrite_files = False
        self.show_removed_dialog = True
        self.confirm_overwrite = True
        self.auto_open_folder = False
        self.lossless_clean = True

        self.rules = {
            "remove_gps": True,
            "remove_timestamps": True,
            "remove_camera": True,
            "remove_xmp": True,
            "remove_iptc": True,
            "keep_icc": True,
            "keep_orientation": True,
        }

        self.setAcceptDrops(True)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File", "Type", "Status", "Output"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        self.add_button = QPushButton("📁 Add files")
        self.view_metadata_button = QPushButton("🔍 View Metadata")
        self.clean_selected_button = QPushButton("🧹 Clean selected")
        self.clean_all_button = QPushButton("🧹 Clean all")
        self.remove_selected_button = QPushButton("❌ Remove selected")
        self.view_log_button = QPushButton("📜 View log")

        self.lossless_checkbox = QCheckBox("Lossless clean (safe metadata only)")
        self.lossless_checkbox.setChecked(True)

        self.theme_button = QPushButton("🌘")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setFixedSize(36, 36)
        self.theme_button.setToolTip("Toggle theme")

        self.settings_button = QPushButton("⚙️ Settings")

        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setValue(0)

        self.preview_panel = PreviewPanel()
        self.brand_label = QLabel("Metadata Cleaner for Windows — by Thrax")

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.add_button)
        top_layout.addWidget(self.view_metadata_button)
        top_layout.addWidget(self.clean_selected_button)
        top_layout.addWidget(self.clean_all_button)
        top_layout.addWidget(self.remove_selected_button)
        top_layout.addWidget(self.view_log_button)
        top_layout.addStretch()
        top_layout.addWidget(self.lossless_checkbox)
        top_layout.addWidget(self.settings_button)
        top_layout.addWidget(self.theme_button)

        bottom_splitter = QSplitter(Qt.Horizontal)

        brand_container = QWidget()
        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.addWidget(self.brand_label)
        brand_layout.addStretch()
        brand_container.setLayout(brand_layout)

        bottom_splitter.addWidget(brand_container)
        bottom_splitter.addWidget(self.preview_panel)
        bottom_splitter.setSizes([300, 400])

        main_layout = QVBoxLayout()
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.progress)
        main_layout.addWidget(bottom_splitter)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.add_button.clicked.connect(self.add_files)
        self.view_metadata_button.clicked.connect(self.view_metadata)
        self.clean_selected_button.clicked.connect(self.clean_selected)
        self.clean_all_button.clicked.connect(self.clean_all)
        self.remove_selected_button.clicked.connect(self.remove_selected_rows)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.settings_button.clicked.connect(self.open_settings)
        self.lossless_checkbox.stateChanged.connect(self.update_lossless_state)
        self.view_log_button.clicked.connect(self.open_log_window)
        self.table.selectionModel().selectionChanged.connect(self.update_preview_from_selection)

        self.apply_theme(self.current_theme)
        log("Application started")

    def start_fade_in(self):
        self.setWindowOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(600)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def apply_theme(self, theme: str):
        if theme == "dark":
            self.setStyleSheet(DARK_STYLESHEET)
            self.current_theme = "dark"
            self.theme_button.setText("🌘")
        else:
            self.setStyleSheet(LIGHT_STYLESHEET)
            self.current_theme = "light"
            self.theme_button.setText("☀")
        log(f"Theme applied: {self.current_theme}")

    def toggle_theme(self):
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme(new_theme)

        rect = self.theme_button.geometry()
        anim = QPropertyAnimation(self.theme_button, b"geometry")
        anim.setDuration(150)
        anim.setStartValue(rect)
        anim.setEndValue(QRect(rect.x(), rect.y() - 3, rect.width(), rect.height()))
        anim.setLoopCount(2)
        anim.finished.connect(lambda: self.theme_button.setGeometry(rect))
        anim.start()
        self._theme_anim = anim

    def update_lossless_state(self, state):
        self.lossless_clean = state == Qt.Checked
        log(f"Lossless clean set to: {self.lossless_clean}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path:
                self.add_file_row(path)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select files", str(Path.home()))
        for f in files:
            self.add_file_row(f)

    def add_file_row(self, path):
        row = self.table.rowCount()
        self.table.insertRow(row)

        file_item = QTableWidgetItem(path)
        file_item.setFlags(file_item.flags() ^ Qt.ItemIsEditable)

        file_type_raw = get_file_type(Path(path))
        icon_prefix = {
            "image": "🖼 ",
            "media": "🎞 ",
            "pdf": "📄 ",
            "other": "❔ ",
        }.get(file_type_raw, "")
        type_item = QTableWidgetItem(icon_prefix + file_type_raw)
        type_item.setFlags(type_item.flags() ^ Qt.ItemIsEditable)

        status_item = QTableWidgetItem("Pending")
        status_item.setFlags(status_item.flags() ^ Qt.ItemIsEditable)

        output_item = QTableWidgetItem("")
        output_item.setFlags(output_item.flags() ^ Qt.ItemIsEditable)

        self.table.setItem(row, 0, file_item)
        self.table.setItem(row, 1, type_item)
        self.table.setItem(row, 2, status_item)
        self.table.setItem(row, 3, output_item)

        log(f"File added to table: {path}")

    def remove_selected_rows(self):
        selected_rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        if not selected_rows:
            QMessageBox.information(self, "No selection", "Select at least one row to remove.")
            return
        for row in selected_rows:
            path_item = self.table.item(row, 0)
            path = path_item.text() if path_item else ""
            self.table.removeRow(row)
            log(f"Row removed from table: {path}")

    def update_preview_from_selection(self, selected, deselected):
        indexes = self.table.selectedIndexes()
        if not indexes:
            self.preview_panel._show_empty()
            return
        row = indexes[0].row()
        path = self.table.item(row, 0).text()
        type_text = self.table.item(row, 1).text()
        file_type = type_text.split(" ", 1)[-1]
        self.preview_panel.show_preview(path, file_type)

    def view_metadata(self):
        selected = self.table.selectedIndexes()
        if not selected:
            QMessageBox.information(self, "No selection", "Select a file first.")
            return

        row = selected[0].row()
        path = self.table.item(row, 0).text()
        type_text = self.table.item(row, 1).text()
        file_type = type_text.split(" ", 1)[-1]

        metadata = extract_metadata(path, file_type)
        dialog = MetadataDialog(metadata, "Metadata Viewer", self)
        dialog.exec()

    def clean_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "No selection", "Select at least one file.")
            return
        self._clean_rows(rows)

    def clean_all(self):
        rows = list(range(self.table.rowCount()))
        if not rows:
            QMessageBox.information(self, "No files", "Add files first.")
            return
        self._clean_rows(rows)

    def _clean_rows(self, rows):
        total = len(rows)
        self.progress.setMaximum(total)
        self.progress.setValue(0)

        local_overwrite = self.overwrite_files
        if self.overwrite_files and self.confirm_overwrite:
            reply = QMessageBox.question(
                self,
                "Confirm overwrite",
                "You chose to overwrite original files.\n"
                "This cannot be undone. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.No:
                local_overwrite = False

        first_output_folder = None

        for i, row in enumerate(rows, start=1):
            path = self.table.item(row, 0).text()
            type_text = self.table.item(row, 1).text()
            file_type = type_text.split(" ", 1)[-1]

            status_item = self.table.item(row, 2)
            output_item = self.table.item(row, 3)

            before = extract_metadata(path, file_type)

            status_item.setText("Cleaning...")
            QApplication.processEvents()

            ok, msg, out_path = clean_file(
                path,
                overwrite=local_overwrite,
                lossless=self.lossless_clean,
                rules=self.rules,
            )

            after = extract_metadata(out_path, file_type) if ok else {}
            removed = compare_metadata(before, after) if ok else {}

            status_item.setText("Cleaned" if ok else "Error")
            output_item.setText(out_path if ok else msg)

            if ok and first_output_folder is None:
                first_output_folder = str(Path(out_path).parent)

            if self.show_removed_dialog and ok:
                dialog = MetadataDialog(removed, "Metadata Removed", self)
                dialog.exec()

            self.progress.setValue(i)
            QApplication.processEvents()

        QMessageBox.information(self, "Done", "Cleaning finished.")

        if self.auto_open_folder and first_output_folder:
            try:
                subprocess.Popen(["explorer", first_output_folder])
            except Exception as e:
                log(f"Failed to open folder {first_output_folder}: {e}")

    def open_settings(self):
        dialog = SettingsWindow(
            overwrite_files=self.overwrite_files,
            show_removed_dialog=self.show_removed_dialog,
            confirm_overwrite=self.confirm_overwrite,
            auto_open_folder=self.auto_open_folder,
            rules=self.rules,
            parent=self,
        )
        if dialog.exec():
            settings = dialog.get_settings()
            self.overwrite_files = settings["overwrite_files"]
            self.confirm_overwrite = settings["confirm_overwrite"]
            self.show_removed_dialog = settings["show_removed_dialog"]
            self.auto_open_folder = settings["auto_open_folder"]
            self.rules = settings["rules"]
            log(f"Settings updated: {settings}")

    def open_log_window(self):
        dlg = LogWindow(self)
        dlg.resize(700, 400)
        dlg.exec()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.start_fade_in()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
