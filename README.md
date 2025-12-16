# Introduction

Project is written with django 6.0 and python 3.14 in mind.

## Requirements

- Python 3.10+
- pip

# Getting Started

First clone the repository from Github and switch to the new directory:

    $ git clone https://github.com/H1mka/pharmaceutical-warehouse-server

Activate the virtualenv for your project.

Install project dependencies:

    $ pip install -r requirements/local.txt

Create a virtual environment (venv):

    $ python -m venv .venv

Install dependencies:

    $ pip install -r requirements.txt

You can now run the development server:

    $ python ./manage.py runserver

# Creating Django Apps (Modules)

All Django applications in this project must be located inside the apps/ directory.

Create a new module:

    $ python manage.py startapp module_name apps/module_name

After creating the app, make sure to:

1. Open apps/your_module_name/apps.py
2. Change the name attribute to name = 'apps.your_module_name'
3. Register the app in config/settings.py:

```
   INSTALLED_APPS = [
   ...other apps,
   "apps.your_module_name",
   ]
```
