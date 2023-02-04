import glob
import subprocess
import os
import multiprocessing


def process(fn):
    i_file = os.path.basename(fn)
    o_file = os.path.splitext(i_file)[0]

    ofp = os.path.join("output", o_file + ".stl")

    ret = subprocess.run(["./cq-cli/cq-cli", "--codec", "stl", "--infile", "keyboard.py",
                          "--outfile", ofp,
                          "--params", "i:{}".format(fn)])

    assert(ret.returncode == 0)
    assert os.path.isfile(ofp), "File {} doesn't exist".format(ofp)

    return o_file


files = glob.glob("configs/*.json")
files.sort()

results = multiprocessing.Pool().imap(process, files)
for i, fn in enumerate(results):
    print("({}/{}) Generated file: {}".format(i + 1, len(files), fn))
