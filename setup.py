import setuptools


def read_file(filepath):
    with open(filepath) as f:
        return f.read()


setuptools.setup(
    name='robopom',
    version=read_file("VERSION"),
    description='Page Object Model for Robot Framework',
    long_description=read_file("README.md"),
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
    install_requires=read_file('requirements.txt').splitlines(),
    entry_points={
        'console_scripts': ['robopom=robopom.cli.robopom:robopom_entry']
    },
    # test_suite="tests"
)
