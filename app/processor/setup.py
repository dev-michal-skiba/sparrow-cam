from setuptools import setup, find_packages

setup(
    name="processor",
    version="0.1.0",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.12",
    install_requires=[
        "opencv-python",
    ],
)
