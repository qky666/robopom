*** Settings ***
Test Template   Search in MTP page
Documentation   Search in MTP page. Check results include given text.
Resource        setup_mtp.resource
Test Setup      Setup Browser
Test Teardown   Close All Browsers



*** Test Cases ***                            # search          result
MTP. TC002_01. Search Brasil in MTP page        Brasil          El ‘logo viajero’ de MTP ha vuelto a la oficina
MTP. TC002_02. Search México in MTP page        México          El valor de los principios de diseño UX
MTP. TC002_03. Search Oficinas in MTP page      Oficinas        En MTP, empresa que desarrolla su actividad en el sector del aseguramiento de negocios digitales


*** Keywords ***
Search in MTP page
    [Arguments]     ${search}   ${result}
    mtp_home_page.Wait Until Loaded
    Set Field Value     pom:search_text        ${search}
    Click Button        pom:mtp_home_page search_button
    mtp_search_results_page.Wait Until Loaded
    Assert Result With Text Exists      ${result}
