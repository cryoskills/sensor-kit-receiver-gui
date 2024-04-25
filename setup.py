from setuptools import setup, find_packages

setup(
    name="cryoskills",
    # Configure setuptools to look for packages in src/
    package_dir = {
        "" : "src"
    },
    include_package_data=True,
    version='0.0.1',
    description='TkInter GUI and CSV logger for receiving CryoSkills packets',
    author='Jono Hawkins',
    author_email='hawkinsj22@cardiff.ac.uk',
    entry_points = {
        "gui_scripts" : [
            "cryoskills-receiver = cryoskills:launch_gui_instance"
        ],
        "console_scripts" : [
            "cryoskills-receiver-gui = cryoskills:launch_gui_instance"
        ]
    },
    install_requires = [
        'contourpy>=1.2',
        'cycler>=0.12.1',
        'fonttools>=4.50',
        'kiwisolver>=1.4',
        'matplotlib>=3.7',
        'numpy>=1.26',
        'packaging>=24.0',
        'pillow>=10.3',
        'pyparsing>=3.1',
        'pyserial>=3.5',
        'python-dateutil>=2.9',
        'six>=1.16'
    ]
)