*** Settings ***
Documentation     Omnia tests
Resource          ../../robopom_pages.resource

*** Variables ***
${USER}             firstname.lastname@mtp.es       # Override this variable!
${PASSWORD}         Password                        # Override this variable!
${NAME}             Firsname Lastname               # Override this variable!
${CAPACITY}         8.00
${SIGNED_UP}        2012-09-17


** Test Cases ***    
Omnia. TC001. Operaciones básicas en Omnia
    omnia_login_page.Wait Until Loaded
    Perform     ${OMNIA_LOGIN_PAGE__USERNAME}               ${USER}
    ...         ${OMNIA_LOGIN_PAGE__PASSWORD}               ${PASSWORD}
    ...         ${OMNIA_LOGIN_PAGE__SUBMIT}                 ${ACTION_CLICK}
    omnia_main_page.Wait Until Loaded
    Perform     ${OMNIA_MAIN_PAGE__LOGGEDAS}                  ${ASSERT_EQUALS}${USER}
    ...         ${OMNIA_MAIN_PAGE__LOGGEDAS}                  ${ACTION_CLICK}
    omnia_user_page.Wait Until Loaded
    ${search}   Generate Random String
    ${search}   Catenate    My random search    ${search}
    Perform     ${OMNIA_USER_PAGE__NAME}                          ${ASSERT_EQUALS}${NAME}
    ...         ${OMNIA_USER_PAGE__EMAIL}           ${ASSERT_EQUALS}${USER}
    ...         ${OMNIA_USER_PAGE__CAPACITY}        ${ASSERT_EQUALS}${CAPACITY}
    ...         ${OMNIA_USER_PAGE__SIGNED_UP}       ${ASSERT_EQUALS}${SIGNED_UP}
    ...         ${OMNIA_USER_PAGE__SEARCH}                      ${search}
    omnia_search_results_page.Wait Until Loaded
    Perform     ${OMNIA_SEARCH_RESULTS_PAGE__SEARCH_RESULTS}      ${ASSERT_EQUALS}${search}
    ...         ${OMNIA_SEARCH_RESULTS_PAGE__ACCOUNT}         ${ACTION_CLICK}
    omnia_account_page.Wait Until Loaded    
    Perform     ${OMNIA_ACCOUNT_PAGE__LOGGEDAS}                              ${ASSERT_EQUALS}${USER}
    ...         ${OMNIA_ACCOUNT_PAGE__FIRSTNAME}                   ${ASSERT_VALUE_IN_EXPECTED}${NAME}
    ...         ${OMNIA_ACCOUNT_PAGE__FIRSTNAME}                   Frodo
    ...         ${OMNIA_ACCOUNT_PAGE__LASTNAME}                    Bolsón
    ...         ${OMNIA_ACCOUNT_PAGE__MAIL}                        frodo.bolson@mtp.es
    ...         ${OMNIA_ACCOUNT_PAGE__LANGUAGE}                    English
    ...         ${OMNIA_ACCOUNT_PAGE__MAIL_NOTIFICATION}          Sin eventos
    ...         ${OMNIA_ACCOUNT_PAGE__NO_SELF_NOTIFIED}           ${False}
    ...         ${OMNIA_ACCOUNT_PAGE__HIDE_MAIL}                  ${True}
    ...         ${OMNIA_ACCOUNT_PAGE__TIME_ZONE}                  (GMT+00:00) London
    ...         ${OMNIA_ACCOUNT_PAGE__COMMENTS}                   En orden cronológico inverso
    ...         ${OMNIA_ACCOUNT_PAGE__WARN_ON_LEAVING_UNSAVED}    ${False}
    ...         ${OMNIA_ACCOUNT_PAGE__LOGOUT}                                ${ACTION_CLICK}
    omnia_login_page.Wait Until Loaded

    
*** Keywords ***
