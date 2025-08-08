# setup.py

from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="datachop",
    version="1.0.0",
    description="A highly flexible and robust library for slicing and processing various data types.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mallikmusaddiq1/datachop",
    author="Mallik Mohammad Musaddiq",
    author_email="mallikmusaddiq1@gmail.com",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="slicing, data, processing, unicode, files, mmap",
    packages=find_packages(),
    python_requires=">=3.7, <4",
    install_requires=[
        # No core dependencies
    ],
    extras_require={
        "full": [
            "regex",
            "Pillow",
            "numpy",
            "charset-normalizer",
            "tqdm",
            "redis",
            "pytest",
        ],
        "dev": [
            "pytest",
            "pytest-cov",
            "twine",
            "black",
            "isort",
            "mypy",
            "pylint",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/mallikmusaddiq1/datachop/issues",
        "Source": "https://github.com/mallikmusaddiq1/datachop",
    },
)