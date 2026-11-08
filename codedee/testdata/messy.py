"""Deliberately messy function so the maintainability scanner has a hotspot."""


def process(data, flag, mode, extra, unused, debug=False):
    total = 0
    if data:
        for x in data:
            if x:
                if flag:
                    if mode == "a":
                        if extra:
                            if debug:
                                total += 1
                            elif extra > 2:
                                total += 2
                            else:
                                total += 3
                        elif extra == 0:
                            total -= 1
                    elif mode == "b":
                        while total < 10:
                            if extra and debug:
                                total += 1
                            else:
                                break
                    else:
                        try:
                            total += int(x)
                        except ValueError:
                            if debug:
                                total = 0
    elif flag or extra or debug:
        total = -1
    return total
