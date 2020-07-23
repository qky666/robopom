*** Settings ***
Library     robopom.Page    page_name=omnia_main_page   WITH NAME   omnia_main_page


*** Keywords ***
Set search
    [Arguments]     ${value}
    Input Text      pom:header search      ${value}
    Press Keys      pom:header search      RETURN
