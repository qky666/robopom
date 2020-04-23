*** Settings ***
Resource    ../../../robopom.resource
Library     robopom.RobopomPage            page_file_path=pages/omnia/account/omnia_account_page      parent_page_name=omnia_main_page    WITH NAME   omnia_account_page


*** Keywords ***
Override Wait Until Loaded
    [Arguments]                                  ${timeout}=${None}                     ${set_library_search_order}=${True}
    omnia_account_page.Core Wait Until Loaded    ${timeout}                             set_library_search_order=${set_library_search_order}
    ${loggedas} =                                omnia_account_page.Perform Get Text    ${OMNIA_ACCOUNT_PAGE__LOGGEDAS}
    omnia_account_page.Assert Equals             ${OMNIA_ACCOUNT_PAGE__ACTIVE_USER}     ${loggedas}
    