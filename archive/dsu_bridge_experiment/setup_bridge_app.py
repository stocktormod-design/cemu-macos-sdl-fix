from setuptools import setup

APP = ["8bitdo_dsu_bridge_ui.py"]
DATA_FILES = ["8bitdo_dsu_bridge.py"]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "8BitDo DSU Bridge v7.6.6",
        "CFBundleDisplayName": "8BitDo DSU Bridge v7.6.6",
        "CFBundleIdentifier": "local.tormodholand.8bitdo-dsu-bridge-v7-6-6",
        "CFBundleVersion": "1.0.27",
        "CFBundleShortVersionString": "1.0.27",
        "LSMinimumSystemVersion": "11.0",
    },
    "packages": ["pygame"],
    "includes": ["tkinter"],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
