*** Settings ***
Library     SeleniumLibrary    timeout=${TIMEOUT}    plugins=robopom.RobopomPlugin     run_on_failure=On Failure
# Library     DebugLibrary


*** Variables ***
${TIMEOUT}      5
${BROWSER}      Chrome
${MAXIMIZE}     ${False}
${WIDTH}        1366
${HEIGHT}       768
${URL}          https://google.com


*** Keywords ***
On Failure
    Capture Page Screenshot     filename=EMBED
    Log Pom Tree


Setup Browser
    [Tags]              flatten
    Open Browser        ${URL}     ${BROWSER}
    ${real_width}=      Get Variable Value  ${WIDTH}
    ${real_height}=     Get Variable Value  ${HEIGHT}
    Run Keyword If      $real_width is not None and $real_height is not None    Set Window Size     ${WIDTH}   ${HEIGHT}
    ${real_maximize}=   Get Variable Value  ${MAXIMIZE}
    Run Keyword If      $real_maximize is True    Maximize Browser Window
