import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testauth.settings.local")

if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    args = sys.argv[:]
    args.insert(1, "test")
    execute_from_command_line(args)
