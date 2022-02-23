import glob
import subprocess
import os
import re
import multiprocessing


def process(fn):
    print("Processing config file {}".format(fn))
    i_file = os.path.basename(fn)
    o_file = os.path.splitext(i_file)[0]
    subprocess.run(["./cq-cli/cq-cli", "--codec", "stl", "--infile", "keyboard.py",
                    "--outfile", os.path.join("output", o_file + ".stl"),
                    "--params", "i:{}".format(fn)])
    return o_file


files = glob.glob("configs/*.json")
files.sort()

results = multiprocessing.Pool().imap(process, files)

for i, fn in enumerate(results):
    print("Processed config file {}".format(fn))
