*** Settings ***
Resource    suites/setup_common.resource
Resource    pages/other/test_component.resource
Resource    pages/mtp/mtp_page.resource
Resource    pages/mtp/mtp_home_page.resource
Resource    pages/mtp/mtp_search_results_page.resource


*** Variables ***
${URL}      https://www.mtp.es


*** Keywords ***
