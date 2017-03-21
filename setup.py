from setuptools import setup

version = open('VERSION').read()
setup(
    name='sqlalchemy_opentracing',
    version=version,
    url='https://github.com/carlosalberto/python-sqlalchemy/',
    download_url='https://github.com/carlosalberto/python-sqlalchemy/tarball/'+version,
    license='BSD',
    author='Carlos Alberto Cortez',
    author_email='calberto.cortez@gmail.com',
    description='OpenTracing support for SQLAlchemy',
    long_description=open('README.rst').read(),
    packages=['sqlalchemy_opentracing'],
    platforms='any',
    install_requires=[
        'sqlalchemy',
        'opentracing>=1.1,<1.2'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
