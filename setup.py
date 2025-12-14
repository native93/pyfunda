from setuptools import setup, find_packages

setup(
    name="funda",
    version="2.0.0",
    description="Python API for Funda.nl real estate listings",
    author="0xMH",
    url="https://github.com/0xMH/pyfunda",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
    ],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
