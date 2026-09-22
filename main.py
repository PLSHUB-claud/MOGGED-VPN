import os
import sys

src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from mogged.app import run

if __name__ == "__main__":
    run()
