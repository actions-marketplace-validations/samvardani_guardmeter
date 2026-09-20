import pathlib
import sys

# Put the project root on sys.path so 'src' is a top-level package
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
