import glob
import subprocess
import os
import re
import multiprocessing


def process(fn):
    print('Converting {} to PNG'.format(fn))
    o_file = os.path.splitext(fn)[0]
    subprocess.run(["convert", "-size", "1200x1200", "-rotate",
                    "45", "-trim", "+repage", fn, o_file + ".png"])
    return o_file


files = glob.glob("output/*.svg")
files.sort()

results = multiprocessing.Pool().map(process, files)

with open('GALLERY.md', 'w') as gf:
    gf.write("# Gallery\n\n")

    for i, fn in enumerate(results):
        gf.write("## {}\n".format(fn))
        gf.write("![image_{}]({})\n\n".format(i, fn + ".png"))
