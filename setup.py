from setuptools import setup, find_packages

install_requires=[
    'contourpy==1.2.1',
    'cycler==0.12.1',
    'fonttools==4.50.0',
    'kiwisolver==1.4.5',
    'matplotlib==3.8.4',
    'numpy==1.26.4',
    'packaging==24.0',
    'pillow==10.3.0',
    'pyparsing==3.1.2',
    'pyserial==3.5',
    'python-dateutil==2.9.0.post0',
    'six==1.16.0'
]

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
            "cryoskills-receiver = cryoskills:launch_new_receiver_gui"
        ]
    },
    install_requires = install_requires
)