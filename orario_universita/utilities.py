import colorsys
import itertools
import random


def random_hex_color():
    while True:
        h, s, l = (
            random.random(),
            0.5 + random.random() / 2.0,
            0.4 + random.random() / 5.0,
        )
        r, g, b = [int(256 * i) for i in colorsys.hls_to_rgb(h, l, s)]
        yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000
        if yiq < 128:
            # ensure text is readable
            break
    return f"#{r:02X}{g:02X}{b:02X}"


# https://stackoverflow.com/a/49819417/13204109
def parse_multi_form(form):
    result = {}
    for full_key in form:
        value = form[full_key]

        key_path = []
        while full_key:
            if "[" in full_key:
                k, r = full_key.split("[", 1)
                key_path.append(k)
                assert r[0] != "]"
                full_key = r.replace("]", "", 1)
            else:
                key_path.append(full_key)
                break

        sub_data = result
        last_key = key_path.pop()
        for k in key_path:
            assert isinstance(sub_data, dict)
            sub_data = sub_data.setdefault(int(k) if k.isdigit() else k, {})
        assert isinstance(sub_data, dict)
        sub_data[last_key] = value

    return result


def iterator_index(it, n):
    return next(itertools.islice(it, n, n + 1))
