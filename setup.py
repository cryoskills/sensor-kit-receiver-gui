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
            "cryoskills-receiver = cryoskills:launch_new_receiver_gui"
        ]
    }
)