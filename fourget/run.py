import argparse
import os
import sys
from fourget import Thread, Image

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("thread_url", help="URL of the 4chan thread")
    parser.add_argument("-o", "--output-dir", help="output images to this directory")
    args = parser.parse_args()

    t = Thread(**Thread.urlparse(args.thread_url))

    if not args.output_dir:
        output_dir = os.path.join(t.board, t.thread)
    else:
        output_dir = args.output_dir

    abs_output_dir = determine_abs_path(output_dir)

    make_dir(abs_output_dir)

    sys.stderr.write("Downloading images of %s to %s\n" % (t.url, abs_output_dir))

    for image in t.iter_images:
        image.get_with_progress_bar = True
        image_path = os.path.join(abs_output_dir, image.filename)
        with open(image_path, 'wb') as f:
            image.save(f)

def determine_abs_path(path):
    if not os.path.isabs(path):
        return os.path.join(os.getcwd(), path)
    return path

def make_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

if __name__ == '__main__':
    run()
