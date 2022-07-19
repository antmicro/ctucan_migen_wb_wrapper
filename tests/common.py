import os


def get_test_output_dir(filename):
    test_dir = os.path.dirname(filename)
    name = os.path.basename(filename)
    output_dirname = os.path.splitext(name)[0]
    return os.path.join(test_dir, "build", output_dirname)
