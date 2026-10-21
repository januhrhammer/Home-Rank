#!/usr/bin/env python
"""Django's command-line entry point: `python manage.py <command>`."""

import os
import sys

from django.core.management import execute_from_command_line


def main() -> None:
    # Local development uses the dev settings unless DJANGO_SETTINGS_MODULE says otherwise.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
