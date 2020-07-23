*** Settings ***
Documentation   Omnia tests
Resource        setup_omnia.resource
Test Setup      Setup Browser
Test Teardown   Close All Browsers


*** Variables ***
${USER}             firstname.lastname@mtp.es       # Override this variable!
${PASSWORD}         Password                        # Override this variable!
${NAME}             Firsname Lastname               # Override this variable!
${CAPACITY}         8.00                            # Override this variable!
${SIGNED_UP}        2012-09-17                      # Override this variable!


*** Test Cases ***
Omnia. TC001. Operaciones básicas en Omnia
    omnia_login_page.Wait Until Loaded
    Set Field Value   pom:username   ${USER}
    Set Field Value   pom:password   ${PASSWORD}
    Click Element     pom:submit

    omnia_main_page.Wait Until Loaded
    Wait Until Field Value Satisfies   pom:loggedas   expected_value=${USER}
    Click Element     pom:loggedas

    omnia_user_page.Wait Until Loaded
    ${search}   Generate Random String
    ${search}   Catenate    My random search    ${search}
    Wait Until Field Value Satisfies   pom:name        expected_value=${NAME}
    Wait Until Field Value Satisfies   pom:email       expected_value=${USER}
    Wait Until Field Value Satisfies   pom:capacity    expected_value=${CAPACITY}
    Wait Until Field Value Satisfies   pom:signed_up   expected_value=${SIGNED_UP}
    Set Field Value    pom:search    ${search}

    omnia_search_results_page.Wait Until Loaded
    Wait Until Field Value Satisfies   pom:search_results    expected_value=${search}
    Click Element   pom:account

    omnia_account_page.Wait Until Loaded
    Wait Until Field Value Satisfies   pom:loggedas    expected_value=${USER}
    Wait Until Field Value Satisfies   pom:firstname   expected_value=${NAME}   compare_function=Value In Expected
    Set Field Value     pom:firstname                  Frodo
    Set Field Value     pom:lastname                   Bolsón
    Set Field Value     pom:mail                       frodo.bolson@mtp.es
    Set Field Value     pom:language                   English
    Set Field Value     pom:mail_notification          Sin eventos
    Set Field Value     pom:no_self_notified           ${False}
    Set Field Value     pom:hide_mail                  ${True}
    Set Field Value     pom:time_zone                  (GMT+00:00) London
    Set Field Value     pom:comments                   En orden cronológico inverso
    Set Field Value     pom:warn_on_leaving_unsaved    ${False}
    Click Element       pom:logout

    omnia_login_page.Wait Until Loaded

    
*** Keywords ***
