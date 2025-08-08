import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="datachop",
    version="1.0.0",
    author="Mallik Mohammad Musaddiq",
    author_email="mallikmusaddiq1@gmail.com", # Apni email yahan daal do
    description="The Ultimate Slicing Module for various data types and files.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mallikmusaddiq1/datachop",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    py_modules=["datachop"], # Isse single file package banega
    python_requires=">=3.8",
    install_requires=[
        'regex>=2024.5.15',
        'charset-normalizer>=3.3.2',
        'Pillow>=10.3.0',
        'moviepy>=1.0.3',
        'ffmpeg-python>=0.2.0',
        'PyPDF2>=3.0.1',
        'python-docx>=1.1.0',
        'odfpy>=1.4.1',
        'pydub>=0.25.1',
        'numpy>=1.26.4',
        'tqdm>=4.66.4',
        'redis>=5.0.4'
    ],
    extras_require={
        'full': [
            'pydub',
            'pillow',
            'moviepy',
            'ffmpeg-python',
            'pypdf2',
            'python-docx',
            'odfpy',
            'numpy',
            'tqdm',
            'redis'
        ]
    }
)
