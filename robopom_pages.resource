*** Variables ***
${URL_MTP}      https://www.mtp.es
${URL_OMNIA}    https://omniamanager.mtp.es/
${BROWSER}      Chrome
${MAXIMIZE}     ${False}
${WIDTH}        1366
${HEIGHT}       768

*** Settings ***
Resource              pages/mtp/mtp_page.resource
Resource              pages/mtp/mtp_home_page.resource
Resource              pages/mtp/mtp_search_results_page.resource
Resource              pages/omnia/omnia_main_page.resource
Resource              pages/omnia/omnia_login_page.resource
Resource              pages/omnia/user/omnia_user_page.resource
Resource              pages/omnia/search_results/omnia_search_results_page.resource
Resource              pages/omnia/account/omnia_account_page.resource


*** Keywords ***
Setup MTP
    [Tags]              flatten
    Open Browser        ${URL_MTP}     ${BROWSER}
    ${real_width}=      Get Variable Value  ${WIDTH}
    ${real_height}=     Get Variable Value  ${HEIGHT}
    Run Keyword If      $real_width is not None and $real_height is not None      Set Window Size     ${WIDTH}   ${HEIGHT}
    ${real_maximize}=   Get Variable Value  ${MAXIMIZE}
    Run Keyword If      $real_maximize is True    Maximize Browser Window


Setup Omnia
    [Tags]              flatten
    Open Browser        ${URL_OMNIA}     ${BROWSER}
    ${real_width}=      Get Variable Value  ${WIDTH}
    ${real_height}=     Get Variable Value  ${HEIGHT}
    Run Keyword If      $real_width is not None and $real_height is not None      Set Window Size     ${WIDTH}   ${HEIGHT}
    ${real_maximize}=   Get Variable Value  ${MAXIMIZE}
    Run Keyword If      $real_maximize is True    Maximize Browser Window
