*** Settings ***
Resource          ../../robopom.resource
Library           robopom.RobopomPage          page_file_path=pages/mtp/mtp_search_results_page    parent_page_name=mtp_page    WITH NAME    mtp_search_results_page


*** Keywords ***
Assert Result With Text Exists
    [Arguments]    ${text}
    ${result}    Add New Page Element Generator Instance    generator=${MTP_SEARCH_RESULTS_PAGE__RESULT_TEXT_GENERATOR}    format_args=${text}
    Wait Until Visible    ${result}
