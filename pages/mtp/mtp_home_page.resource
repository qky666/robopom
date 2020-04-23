*** Settings ***
Resource          ../../robopom.resource
Library           robopom.RobopomPage          page_file_path=pages/mtp/mtp_home_page    parent_page_name=mtp_page    WITH NAME    mtp_home_page


*** Keywords ***
Assert Paragraph With Text Exists
    [Arguments]    ${text}
    ${paragraph}    Add New Page Element Generator Instance    generator=${MTP_HOME_PAGE__PARAGRAPH_GENERATOR}    format_args=${text}
    Wait Until Visible    ${paragraph}
