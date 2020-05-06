from os import path

from setuptools import setup

PROJECT_ROOT = path.dirname(__file__)

with open(path.join(PROJECT_ROOT, "README.rst"), "rt") as f:
    long_description = f.read()

tests_require = [
    "flake8-bandit>=2.1.1",
    "flake8-bugbear>=19.8.0",
    "flake8-isort>=2.7.0",
    "flake8>=3.7.8",
    "hypothesis>=5.10.5",
    "isort>=4.3.21",
    "pep8-naming>=0.8.2",
    "pytest-cov>=2.8.1",
    "pytest>=5.4.1",
]

setup(
    name="gxmpp",
    version="0.1.0",
    description="A green implementation of the glorious XMPP messaging and presence protocol",
    long_description=long_description,
    url="https://github.com/aurieh/gxmpp",
    author="auri",
    author_email="me@aurieh.me",
    license="LGPL-3.0",
    packages=["gxmpp", "gxmpp.util"],
    install_requires=[
        "gevent>=20.5.0",
        "gevent[dnspython]",
        "dnspython>=1.16.0",
        "idna>=2.9",
        "precis-i18n>=1.0.1",
    ],
    tests_require=tests_require,
    extras_require={"testing": tests_require, },
    test_suite="py.test",
    zip_safe=False,
    platforms="any",
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Communications",
        "Topic :: Communications :: Chat",
        "Topic :: Internet :: XMPP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
