*** Settings ***
Resource    ../../../robopom.resource
Library     robopom.RobopomPage            page_file_path=pages/omnia/user/omnia_user_page      parent_page_name=omnia_main_page    WITH NAME   omnia_user_page
Library     String


*** Keywords ***
Get capacity
    ${text} =       Get Text        ${OMNIA_USER_PAGE__CAPACITY}
    ${text} =       Remove String   ${text}                                             Capacidad Diaria:${SPACE}
    [Return]        ${text}


Get signed_up
    ${text} =       Get Text        ${OMNIA_USER_PAGE__SIGNED_UP}
    ${text} =       Remove String   ${text}                                             Inscrito el:${SPACE}
    [Return]        ${text}
