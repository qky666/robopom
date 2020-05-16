*** Settings ***
Documentation     Check that MTP home page shows some given text.
...               Additionally, check that some elements exist in page.
Test Template     Text in MTP home page
Resource          ../../robopom_pages.resource

*** Test Cases ***
MTP. TC001_01. Text in home page that exist
                      MTP es Digital Business Assurance

MTP. TC001_02. Text in home page that do not exist
                      MTP es Digital Business Assurance BRUTAL

*** Keywords ***
Text in MTP home page
    [Arguments]    ${text}
    mtp_home_page.Wait Until Loaded
    Assert Paragraph With Text Exists    ${text}
