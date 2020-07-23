*** Settings ***
Library     robopom.Page    page_name=mtp_home_page     parent_page_name=mtp_page   WITH NAME   mtp_home_page


*** Keywords ***
Assert Paragraph With Text Exists
    [Arguments]     ${text}
    ${paragraph}    Attach New Node To Page     template=paragraph_template    template_args=${text}
    Wait Until Element Is Visible      ${paragraph}
