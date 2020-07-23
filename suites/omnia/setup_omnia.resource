*** Settings ***
Resource    suites/setup_common.resource
Resource    pages/omnia/omnia_main_page.resource
Resource    pages/omnia/omnia_login_page.resource
Resource    pages/omnia/user/omnia_user_page.resource
Resource    pages/omnia/search_results/omnia_search_results_page.resource
Resource    pages/omnia/account/omnia_account_page.resource



*** Variables ***
${URL}      https://omniamanager.mtp.es/


*** Keywords ***
