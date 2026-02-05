from cx_Freeze import setup, Executable

build_options = {
    "packages": ["PySide6"],
    "include_files": [
        ("assets/icons/icon.ico", "icon.ico"),
    ],
}

setup(
    name="MetadataCleaner",
    version="1.0.0",
    description="Metadata Cleaner for Windows",
    options={"build_exe": build_options},
    executables=[
        Executable(
            "main.py",
            base="Win32GUI",
            target_name="MetadataCleaner.exe",
            icon="assets/icons/icon.ico"
        )
    ],
)
