from setuptools import setup, find_packages

setup(
    name="lightanon",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=1.3.0",
        "numpy>=1.20.0",
        "pyarrow>=14.0.0",
        "polars>=0.19.0",
        "pyyaml>=6.0",
    ],
    author="Your Name",
    description="Lightweight data anonymization for ML compliance (152-FZ)",
    python_requires=">=3.9",
    entry_points={
            'console_scripts': [
                'lightanon=lightanon.cli:main',
                ],
              },
)
