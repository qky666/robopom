*** Settings ***
Library           SeleniumLibrary    timeout=${TIMEOUT}    plugins=robopom.RobopomSeleniumPlugin
Variables         robopom_variables.yaml

*** Variables ***
${TIMEOUT}              5
