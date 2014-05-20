import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()

version = '0.0.1-dev'

requires = [
    'pymongo==2.6.3',
    'pyramid==1.5',
    'pyramid_debugtoolbar==2.0.2',
    'pyramid_jinja2==2.1',
    'pyramid_beaker==0.8',
    'waitress==0.8.9',
    'eduid_am',
] 

if sys.version_info[0] < 3:
    # Babel does not work with Python 3
    requires.append('Babel==1.3')


test_requires = [ 
    'WebTest==2.0.15',
    'mock==1.0.1',
]

docs_extras = [
    'Sphinx==1.2.2'
]


testing_extras = test_requires + [
    'nose==1.3.3',
    'coverage==3.7.1',
    'nosexcover==1.0.10',
]

setup(name='eduid_actions',
      version=version,
      description=('Interrupt the login process in eduid-IdP '
                   'with arbitrary actions'),
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        ],
      author_email='',
      keywords='web pyramid pylons',
      author='NORDUnet A/S',
      url='https://github.com/SUNET/eduid-actions',
      license='BSD',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=test_requires,
      extras_require={
          'docs': docs_extras,
          'testing': testing_extras,
      },
      test_suite="eduid_actions",
      entry_points="""\
      [paste.app_factory]
      main = eduid_actions:main
      """,
      )
