# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name="appy",
    version=__import__('appy.version').version.short,
    license="GPL",
    keywords="pod, pdf, odt, document, plone, django",

    author="Gaetan Delannay",
    author_email="gaetan.delannay@geezteem.com",

    maintainer='Alexander Ivanov',
    maintainer_email='alexander.vl.ivanov@gmail.com',

    url="http://appyframework.org",
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Environment :: Web Environment',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    packages=find_packages(),
    install_requires=[],
    include_package_data=True,
    zip_safe=False,
)
