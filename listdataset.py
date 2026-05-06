import argparse
import os
import sys
import time
import math
import re
from multiprocessing import Process, Queue
from typing import List, Tuple, Optional

def list_datasets(base_dir: str) -> List[str]:
    entries = []
    for d in sorted(os.listdir(base_dir)):
        p = os.path.join(base_dir, d)
        if os.path.isdir(p):
            entries.append(d)
    return entries


base_dir = "/home/dcslab/iot/datasets/"
datasets = list_datasets(base_dir)

print("Datasets under base-dir:")
for i, d in enumerate(datasets):
    print(f"  {i}: {d}")
