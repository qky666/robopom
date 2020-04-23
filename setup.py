import setuptools

setuptools.setup(
    name='robopom',
    version='0.1.0',
    description='robopom package',
    author='José Torrecilla Álvarez',
    author_email='jose.torrecilla@mtp.es',
    license='MIT',
    url="https://github.com/qky666/robopom",
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
