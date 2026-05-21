import sys
import os

# Make src/ and streamlit/ importable when pytest runs from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "streamlit"))
