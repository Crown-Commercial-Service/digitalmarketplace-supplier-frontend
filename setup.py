"""
Common utils for Digital Marketplace apps.
"""

from setuptools import setup, find_packages

setup(
    name='dto-digitalmarketplace-supplier-frontend',
    version='528',
    url='https://github.com/ausdto/dto-digitalmarketplace-supplier-frontend',
    license='MIT',
    author='GDS Developers',
    description='Supplier frontend',
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'Flask',
        'python-dateutil',
        'markdown',
        'newrelic',
        'dto-digitalmarketplace-utils',
        'dto-digitalmarketplace-content-loader',
        'dto-digitalmarketplace-apiclient'
    ]
)
