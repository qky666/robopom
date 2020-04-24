import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name='robopom',
    version='0.1.0',
    description='Page Object Model for Robot Framework',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='José Torrecilla Álvarez',
    author_email='jose.torrecilla@gmail.com',
    license='Apache 2.0',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Framework :: Robot Framework",
        "Framework :: Robot Framework :: Library",
        "Environment :: Web Environment",
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
    ],
    url="https://github.com/qky666/robopom",
    python_requires='>=3.7',
    packages=setuptools.find_packages(),
    package_data={'robopom.resources': ['*'],
                  'robopom.resources.template_files': ['*'], },
    include_package_data=True,
    install_requires=['robotframework==3.1.2',
                      'robotframework-seleniumlibrary==4.3.0',
                      'anytree==2.8.0',
                      'pyyaml==5.3.1',
                      'robotframework-lint==1.0',
                      'click==7.1.1', ],
    entry_points={
        'console_scripts': ['robopom=robopom.cli.robopom:robopom_entry']
    },
    # test_suite="tests"
)
