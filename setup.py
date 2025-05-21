from setuptools import setup, find_packages

setup(
    name="epic-free-games",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'requests>=2.31.0',
        'python-dotenv>=1.0.0',
        'jmespath>=1.0.1',
        'discord-webhook>=1.2.1',
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'epic-free-games=main:main',
        ],
    },
)
