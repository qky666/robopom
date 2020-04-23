*** Settings ***
Resource          ../../robopom.resource
Library           robopom.RobopomPage          page_file_path=pages/omnia/omnia_main_page    WITH NAME    omnia_main_page


*** Keywords ***
Set search
    [Arguments]             ${value}=${None}
    Return From Keyword If  $value is None
    Input Text              ${OMNIA_MAIN_PAGE__SEARCH}  ${value}
    Press Keys              ${OMNIA_MAIN_PAGE__SEARCH}  RETURN
