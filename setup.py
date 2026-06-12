from setuptools import setup

setup(
    name="stockvid",
    version="0.1.0",
    description="Batch download free stock videos from Pexels, Pixabay, and Mixkit",
    py_modules=["stockvid"],
    python_requires=">=3.10",
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
    ],
    entry_points={
        "console_scripts": [
            "stockvid=stockvid:main",
        ],
    },
)
