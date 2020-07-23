*** Settings ***
Library     robopom.Page  page_name=omnia_account_page      parent_page_name=omnia_main_page    WITH NAME   omnia_account_page


*** Keywords ***
Override Wait Until Loaded
    [Arguments]                         ${timeout}=${None}
    Super Wait Until Loaded             ${timeout}
    ${loggedas}=                        Get field value     pom:loggedas
    Wait Until Field Value Satisfies    pom:active_user     expected_value=${loggedas}
