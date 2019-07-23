from setuptools import setup

version = open('VERSION').read()
setup(
    name='sqlalchemy_opentracing',
    version=version,
    url='https://github.com/opentracing-contrib/python-sqlalchemy/',
    download_url='https://github.com/opentracing-contrib/python-sqlalchemy/tarball/'+version,
    license='Apache License 2.0',
    author='Carlos Alberto Cortez',
    author_email='calberto.cortez@gmail.com',
    description='OpenTracing support for SQLAlchemy',
    long_description=open('README.rst').read(),
    packages=['sqlalchemy_opentracing'],
    platforms='any',
    install_requires=[
        'sqlalchemy',
        'opentracing>=1.1,<=2.2'
    ],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
