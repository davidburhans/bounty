def is_osx():
    import platform
    return platform.system() == 'Darwin'


def extract_name(path):
    return splitext(path)[0]


DEFAULT_TIME_SKIP = 0.025  # approximately .5 letters
DEFAULT_PADDING = DEFAULT_TIME_SKIP * 10
DEFAULT_FRAME_SKIP = 128
