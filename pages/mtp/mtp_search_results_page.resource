*** Settings ***
Library     robopom.Page    page_name=mtp_search_results_page   parent_page_name=mtp_page   WITH NAME   mtp_search_results_page


*** Keywords ***
Assert Result With Text Exists
    [Arguments]    ${text}
    ${result}    Attach New Node To Page    template=result_text_template    template_args=${text}
    Wait Until Element Is Visible    ${result}
