# robopom

Page Object Model for Robot Framework

# Installation

Run `pip install -U robopom` to install latest version from [PyPi](https://pypi.org/project/robopom).

# Basics

First, you will need to know how [Robot Framework](https://robotframework.org/) works. 
[Robot Framework User Guide](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html)
has everything you need to know (and a lot more).

Second, you will need to know about [SeleniumLibrary](https://github.com/robotframework/SeleniumLibrary/), 
a Robot Framework library for web testing that uses [Selenium](https://www.selenium.dev/).

# Template

Run `robopom template` to generate a sample project skeleton in current folder. 

## `robopom.resource` file

Here `SeleniumLibrary` is imported.

Some other `global` resources (including, but not limited to, `variables`) can be defined here.
This file should be imported in every "page file" (`page_name.resource`).

## `pages` folder

Hera are the "pages files". These are `*.resource` files that represent a single html page.
  