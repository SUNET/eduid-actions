import os
import sys

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'README.rst')).read()
CHANGES = open(os.path.join(here, 'CHANGES.rst')).read()

try:
    from babel.messages import frontend as babel
except ImportError:
    print("Babel is not installed, you can't localize this package")
    cmdclass = {}
else:
    cmdclass = {
        'compile_catalog': babel.compile_catalog,
        'extract_messages': babel.extract_messages,
        'init_catalog': babel.init_catalog,
        'update_catalog': babel.update_catalog
    }

version = '0.1.1b1'

requires = [
    'six >= 1.11.0',
    'pyramid==1.5',
    'pyramid_debugtoolbar==2.0.2',
    'pyramid_jinja2==2.1',
    'pyramid_beaker==0.8',
    'waitress>=0.8.9',
    'eduid_am>=0.6.1',
    'eduid_userdb>=0.0.4b3',
    'eduid_common[webapp]>=0.1.3b5',
]

if sys.version_info[0] < 3:
    # Babel does not work with Python 3
    requires.append('Babel==1.3')
    requires.append('lingua==1.5')


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
      cmdclass=cmdclass,
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
