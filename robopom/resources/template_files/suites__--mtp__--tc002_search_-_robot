*** Settings ***
Resource            ../../robopom_pages.resource
Test Template       Search in MTP page
Documentation       Search in MTP page. Check results include given text.


*** Test Cases ***                              search          result
MTP. TC002_01. Search Brasil in MTP page        Brasil          El ‘logo viajero’ de MTP ha vuelto a la oficina
MTP. TC002_02. Search México in MTP page        México          El valor de los principios de diseño UX
MTP. TC002_03. Search Oficinas in MTP page      Oficinas        En MTP, empresa que desarrolla su actividad en el sector del aseguramiento de negocios digitales


*** Keywords ***
Search in MTP page
    [Arguments]     ${search}   ${result}
    mtp_home_page.Wait Until Loaded
    Perform     ${MTP_PAGE__SEARCH_TEXT}        ${search}
    ...         ${MTP_PAGE__SEARCH_BUTTON}      ${ACTION_CLICK}
    mtp_search_results_page.Wait Until Loaded
    Assert Result With Text Exists      ${result}
