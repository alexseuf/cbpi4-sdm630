from setuptools import setup
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="cbpi4-sdm630",
    version="0.1.2",
    description="CraftBeerPi4 SDM630 Modbus RTU power sensor plugin",
    author="Alexander Seufert",
    include_package_data=True,
    packages=["cbpi4-sdm630"],
    package_data={"cbpi4-sdm630": ["*"]},
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=["minimalmodbus>=2.1.1", "pyserial>=3.5"],
)
