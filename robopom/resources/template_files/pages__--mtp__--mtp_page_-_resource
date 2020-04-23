*** Settings ***
Resource          ../../robopom.resource
Library           robopom.RobopomPage          page_file_path=pages/mtp/mtp_page    WITH NAME    mtp_page


*** Keywords ***
Set search_text
    [Arguments]    ${value}
    Click Element    ${MTP_PAGE__SEARCH_ICON}
    Input Text    ${MTP_PAGE__SEARCH_TEXT}    ${value}
    