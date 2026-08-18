# -*- coding: utf-8 -*-
"""让 ``python -m download_organizer`` 成为可用入口。"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
