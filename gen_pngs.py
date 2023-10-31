import glob
import subprocess
import os
import multiprocessing


def process(fn):
    print('Converting {} to PNG'.format(fn))
    o_file = os.path.splitext(fn)[0]
    subprocess.run(["convert", "-size", "1200x1200", "-rotate",
                    "45", "-trim", "+repage", fn, o_file + ".png"])
    return o_file


def adjust_name(fn):
    fs = fn.split('_')
    fc = 4 - len(list(filter(lambda c: c.isdigit(), fs[1])))
    fs[1] = ('0' * fc) + fs[1]
    return '_'.join(fs)


files = glob.glob("output/*.svg")
files.sort(key=adjust_name)

results = multiprocessing.Pool().imap(process, files)

with open('GALLERY.md', 'w') as gf:
    gf.write("# Gallery\n\n")

    for i, fn in enumerate(results):
        fn = os.path.join("images", *os.path.split(fn)[1:]) 
        gf.write("## {}\n".format(fn))
        gf.write("![image_{}]({})\n\n".format(i, fn + ".png"))
