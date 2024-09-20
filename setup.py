import setuptools

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name='haneda-parking',
    version='0.0.1',
    install_requires=requirements,
    packages=['haneda_parking'],
)
