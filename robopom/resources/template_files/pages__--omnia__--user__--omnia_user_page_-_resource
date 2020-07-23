*** Settings ***
Library   robopom.Page   page_name=omnia_user_page   parent_page_name=omnia_main_page   WITH NAME   omnia_user_page
Library   String


*** Keywords ***
Get capacity
    ${text}=   Get Text        pom:capacity
    ${text}=   Remove String   ${text}        Capacidad Diaria:${SPACE}
    [Return]   ${text}


Get signed_up
    ${text}=   Get Text        pom:signed_up
    ${text}=   Remove String   ${text}        Inscrito el:${SPACE}
    [Return]        ${text}
