import glob
import subprocess
import os
import multiprocessing
from progress.bar import Bar


def process(fn):
    i_file = os.path.basename(fn)
    o_file = os.path.splitext(i_file)[0]

    ret = subprocess.run(["./cq-cli/cq-cli", "--codec", "stl", "--infile", "keyboard.py",
                                 "--outfile", os.path.join("output",
                                                           o_file + ".stl"),
                                 "--params", "i:{}".format(fn)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
    assert(ret.returncode == 0)
    return o_file


files = glob.glob("configs/*.json")
files.sort()

results = multiprocessing.Pool().imap(process, files)

with Bar('Processing', max=len(files),
         suffix='%(percent).1f%% - %(eta)ds') as bar:
    for i, fn in enumerate(results):
        bar.next()
