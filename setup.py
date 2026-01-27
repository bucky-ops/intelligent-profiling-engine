from setuptools import setup, find_packages

setup(
    name="profile_system",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "scikit-learn",
        "pandas",
        "numpy",
        "matplotlib",
        "seaborn",
        "nltk",
        "spacy",
        "transformers",
        "streamlit",
    ],
)