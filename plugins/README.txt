Plugins are python packages and should be placed in this directory.

The correct file hierarchy  looks like:
Arelle
├── Arelle.egg-info
├── License.txt
├── README.txt
├── arelle
│   ├── Cntlr.py
│   ├── ... Arelle source code
├── arelle.pyw, etc.
└── plugins
    ├── README.txt
    ├── my_plugin
    │   └── __init__.py
    └── hello_dolly
        └── __init__.py
