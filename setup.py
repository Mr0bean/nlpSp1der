"""
Setup script for newsletter system.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    requirements = requirements_path.read_text().strip().split('\n')
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]

setup(
    name="newsletter-crawler",
    version="1.0.0",
    description="A focused solution for crawling newsletter content",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Newsletter System Team",
    python_requires=">=3.8",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            # 统一指向已存在的基础运行脚本
            "newsletter-crawler=newsletter_system.scripts.run:main",
            "newsletter-basic=newsletter_system.scripts.run:main",
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="newsletter crawler web-scraping content-extraction",
    project_urls={
        "Documentation": "https://github.com/your-org/newsletter-system/docs",
        "Source": "https://github.com/your-org/newsletter-system",
        "Tracker": "https://github.com/your-org/newsletter-system/issues",
    },
)