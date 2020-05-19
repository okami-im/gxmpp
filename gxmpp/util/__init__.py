def reraise(tp, value, tb=None):
    # Taken from:
    # https://github.com/benjaminp/six/blob/3a3db7510b33eb22c63ad94bc735a9032949249f/six.py#L697
    # Licensed under the MIT license
    # Copyright (c) 2010-2020 Benjamin Peterson
    try:
        if value is None:
            value = tp()
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value
    finally:
        value = None
        tb = None
