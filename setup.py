from setuptools import setup, find_packages

setup(
    name="lightanon",
    version="0.3.0",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=[
        "pandas>=1.3.0",
        "numpy>=1.20.0",
        "pyarrow>=14.0.0",
        "polars>=0.19.0",
        "pyyaml>=6.0",
        "cryptography>=42.0.0",
        "filelock>=3.13.0",
    ],
    author="Alexander Soldatov",
    description="Lightweight data anonymization for ML compliance (152-FZ)",
    license="MIT",
    python_requires=">=3.9",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    entry_points={
            'console_scripts': [
                'lightanon=lightanon.cli:main',
                ],
              },
)
