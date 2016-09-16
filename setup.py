"""
stew
--------------
Set programming with TErms reWriting
"""

from setuptools import setup


setup(
    name='stew',
    version='0.1',
    url='https://github.com/kyouko-taiga/stew',
    license='Apache 2',
    author='Dimitri Racordon',
    author_email = "kyouko.taiga@gmail.com",
    description='Domain specific language for term rewriting.',
    long_description=__doc__,
    keywords='term rewriting albebraic specifications',
    packages=['stew'],
    include_package_data=True,
    platforms='any',
    install_requires=[
        'astunparse>=1.4.0'
    ],
    test_suite='tests',
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries'
    ]
)
